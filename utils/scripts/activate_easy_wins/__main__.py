import argparse
import subprocess
import sys
from os import environ
from pathlib import Path

import yaml
from utils.const import COMPONENT_GROUPS
from ._internal.const import ARTIFACT_URL, SKIPPED_NODES_FILE
from ._internal.core import update_manifest
from ._internal.logger import ActivationLogger
from ._internal.test_artifact import parse_artifact_data, pull_artifact
from ._internal.manifest_editor import ManifestEditor

MANIFESTS_DIR = Path("manifests/")


def _owner_to_branch(owner: str, components: list[str] | None = None) -> str:
    name = owner.rsplit("/", maxsplit=1)[-1] if "/" in owner else owner
    branch = f"easy-win/{name or 'no-code-owner'}"
    if components:
        branch += f"/{'-'.join(sorted(components))}"
    return branch


def _git(*args: str) -> None:
    subprocess.run(["git", *args], check=True)


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
    parser.add_argument(
        "--split-co",
        action="store_true",
        help="Commits the changes to a different git branch for each test owner",
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

    test_data, weblogs, owners = parse_artifact_data(
        Path("data/"), libraries_to_process, excluded_owners=excluded_owners, use_dev=args.dev
    )

    has_updates = False
    if args.split_co:
        base_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
        activations_per_owner: dict[str, int] = {}
        for owner in owners:
            manifest_editor = ManifestEditor(weblogs, components=libraries_to_process)
            logger = update_manifest(manifest_editor, test_data, skipped_nodes, owner)
            created_rules_count = len(manifest_editor.added_rules)
            activations_per_owner[owner or "No code owner"] = logger.total_tests_activated
            owner_has_changes = logger.total_modified_rules > 0 or created_rules_count > 0
            has_updates = has_updates or owner_has_changes

            if not args.dry_run and owner_has_changes:
                branch = _owner_to_branch(owner, args.components)
                _git("checkout", "-B", branch, base_branch)
                manifest_editor.write()
                subprocess.run(["yamlfmt", "manifests/"], check=True)
                subprocess.run(["yamllint", "-s", "manifests/"], check=True)
                subprocess.run(["python", "utils/manifest/format.py"], check=True)
                _git("add", str(MANIFESTS_DIR))
                _git("commit", "-m", f"chore: activate easy wins for {owner or 'no code owner'}")
                _git("checkout", base_branch)
        ActivationLogger.print_split_co_report(activations_per_owner)
    else:
        manifest_editor = ManifestEditor(weblogs, components=libraries_to_process)
        logger = update_manifest(manifest_editor, test_data, skipped_nodes)
        created_rules_count = len(manifest_editor.added_rules)
        logger.print_top_rules()
        logger.print_activation_report()
        logger.print_detailed_rules_report(created_rules_count)

        has_updates = has_updates or logger.total_modified_rules > 0 or created_rules_count > 0

        manifest_editor.write(dry_run=args.dry_run)

    # Exit with status 1 if no updates were made
    if not has_updates:
        sys.exit(1)


if __name__ == "__main__":
    main()
