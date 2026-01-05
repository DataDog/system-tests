import argparse
import sys
from os import environ
from pathlib import Path
from ._internal.const import ARTIFACT_URL, LIBRARIES
from ._internal.core import print_activation_report, print_detailed_rules_report, update_manifest
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
    args = parser.parse_args()

    # Filter libraries if components are specified
    libraries_to_process = args.components if args.components else LIBRARIES
    # Validate that all specified components exist in LIBRARIES
    if args.components:
        invalid_components = [c for c in args.components if c not in LIBRARIES]
        if invalid_components:
            parser.error(f"Invalid components: {invalid_components}. Valid components are: {', '.join(LIBRARIES)}")

    if not args.no_download:
        token = environ["GITHUB_TOKEN"]
        pull_artifact(ARTIFACT_URL, token, Path("data"))

    # Get excluded owners from command line
    excluded_owners: set[str] = set(args.exclude) if args.exclude else set()

    test_data, weblogs = parse_artifact_data(Path("data/"), libraries_to_process, excluded_owners=excluded_owners)

    manifest_editor = ManifestEditor(weblogs, components=libraries_to_process)
    (
        tests_per_language,
        modified_rules_by_level,
        created_rules_count,
        tests_without_rules,
        unique_tests_per_language,
    ) = update_manifest(manifest_editor, test_data)
    total_tests_activated = sum(tests_per_language.values())
    total_unique_tests = sum(unique_tests_per_language.values())
    print_activation_report(tests_per_language, unique_tests_per_language)
    print_detailed_rules_report(
        modified_rules_by_level, created_rules_count, total_tests_activated, total_unique_tests, tests_without_rules
    )

    # Check if any updates were made
    total_modified_rules = sum(modified_rules_by_level.values())
    has_updates = total_modified_rules > 0 or created_rules_count > 0

    if not args.dry_run:
        manifest_editor.write()

    # Exit with status 1 if no updates were made
    if not has_updates:
        sys.exit(1)


if __name__ == "__main__":
    main()
