import argparse
import sys
from os import environ
from pathlib import Path

import yaml
from utils.const import COMPONENT_GROUPS
from ._internal.const import ARTIFACT_URL, SKIPPED_NODES_FILE
from ._internal.core import update_manifest
from ._internal.test_artifact import parse_artifact_data, pull_artifact
from ._internal.manifest_editor import ManifestEditor


def main() -> None:
    parser = argparse.ArgumentParser(description="Activate easy wins from test artifacts")
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Skip downloading the artifact and use existing data directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only display a summary of changes without writing anything to disk",
    )
    parser.add_argument(
        "--components",
        nargs="+",
        help="List of components to process (e.g., python java nodejs). If not \
                specified, all components are processed.",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        help="List of code owners to exclude (e.g., @DataDog/apm-python @DataDog/asm-libraries). \
                Tests owned by these teams will be excluded from activation.",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Use data from dev runs instead of nightly runs",
    )
    args = parser.parse_args()

    # Filter libraries if components are specified
    libraries_to_process = args.components or sorted(COMPONENT_GROUPS.easy_win)
    # Validate that all specified components exist in COMPONENT_GROUPS.easy_win
    if args.components:
        invalid_components = [c for c in args.components if c not in COMPONENT_GROUPS.easy_win]
        if invalid_components:
            valid = ", ".join(sorted(COMPONENT_GROUPS.easy_win))
            parser.error(f"Invalid components: {invalid_components}. Valid components are: {valid}")

    if not args.no_download:
        token = environ["GITHUB_TOKEN"]
        pull_artifact(ARTIFACT_URL, token, Path("data"))

    # Get excluded owners from command line
    excluded_owners: set[str] = set(args.exclude) if args.exclude else set()

    skipped_nodes = yaml.safe_load(SKIPPED_NODES_FILE.read_text())

    test_data, weblogs = parse_artifact_data(
        Path("data/"), libraries_to_process, excluded_owners=excluded_owners, use_dev=args.dev
    )

    manifest_editor = ManifestEditor(weblogs, components=libraries_to_process)
    logger = update_manifest(manifest_editor, test_data, skipped_nodes)
    created_rules_count = len(manifest_editor.added_rules)
    logger.print_top_rules()
    logger.print_activation_report()
    logger.print_detailed_rules_report(created_rules_count)

    has_updates = logger.total_modified_rules > 0 or created_rules_count > 0

    manifest_editor.write(dry_run=args.dry_run)

    # Exit with status 1 if no updates were made
    if not has_updates:
        sys.exit(1)


if __name__ == "__main__":
    main()
