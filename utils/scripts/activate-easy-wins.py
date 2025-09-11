from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

path_root = Path(__file__).parents[2]

FPD_URL = "https://dd-feature-parity.azurewebsites.net/Tests/Groups"

# Status constants
STATUS_MISSING_FEATURE = "missing_feature"
STATUS_BUG = "bug"
STATUS_INCOMPLETE_TEST_APP = "incomplete_test_app"
STATUS_IRRELEVANT = "irrelevant"
STATUS_VARIANT_STRUCTURE = "variant_structure"
STATUS_XPASS = "xpass"
STATUS_PASSED = "passed"
STATUS_XPASSED = "xpassed"

# YAML multiline indicators
YAML_MULTILINE_INDICATORS = [">-", "|-", ">", "|"]

# Special statuses that indicate test is not activated
SPECIAL_STATUSES = [STATUS_BUG, STATUS_MISSING_FEATURE, STATUS_INCOMPLETE_TEST_APP, STATUS_IRRELEVANT]

# Updatable statuses
UPDATABLE_STATUSES = [STATUS_MISSING_FEATURE, STATUS_BUG, STATUS_INCOMPLETE_TEST_APP]

# Test outcomes that qualify as passing
PASSING_OUTCOMES = [STATUS_XPASSED, STATUS_PASSED]

# Language mapping
LANGUAGE_MAP = {2: "dotnet", 3: "nodejs", 4: "php", 5: "python", 6: "golang", 7: "ruby", 8: "java", 9: "cpp"}

# Common strings
MANIFEST_DIR = "manifests"
MANIFEST_EXTENSION = ".yml"
TEST_SEPARATOR = "::"
DEFAULT_VARIANT = "*"

# Error messages
MSG_NOT_IN_MANIFEST = "not_in_manifest"
MSG_HAS_VARIANT_STRUCTURE = "has_variant_structure"
MSG_NOT_A_TEST_CLASS = "not_a_test_class"

# Display constants
MAX_TESTS_TO_SHOW = 3
HTTP_OK = 200
MIN_PARTS_FOR_TEST_CLASS = 2


class ManifestEntry:
    """Represents a test class entry found in a manifest file"""

    def __init__(self, *, line_index: int, status: str, is_multiline: bool, lines_to_replace: int, original_line: str):
        self.line_index = line_index
        self.status = status
        self.is_multiline = is_multiline
        self.lines_to_replace = lines_to_replace
        self.original_line = original_line

    def is_updatable(self) -> bool:
        """Check if this entry can be updated (has updatable status)"""
        return any(self.status.startswith(s) for s in UPDATABLE_STATUSES)

    def is_activated(self) -> bool:
        """Check if this entry is already activated (doesn't have special status)"""
        if self.status == STATUS_VARIANT_STRUCTURE:
            return True
        return not any(self.status.startswith(s) for s in SPECIAL_STATUSES)


class TestStatusInfo:
    """Represents test status information from manifest parsing"""

    def __init__(self, *, status: str | None = None, is_updatable: bool = False, is_activated: bool = False):
        self.status = status
        self.is_updatable = is_updatable
        self.is_activated = is_activated

    @classmethod
    def from_manifest_entry(cls, entry: ManifestEntry) -> TestStatusInfo:
        """Create TestStatusInfo from a ManifestEntry"""
        if entry is None:
            return cls()
        return cls(status=entry.status, is_updatable=entry.is_updatable(), is_activated=entry.is_activated())


def fetch_fpd_data() -> list[dict[str, Any]]:
    """Fetch test data from the Feature Parity Dashboard API"""
    req = urllib.request.Request(FPD_URL, method="GET")  # noqa: S310
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        if resp.status != HTTP_OK:
            raise RuntimeError(f"HTTP {resp.status}")
        return json.load(resp)


def extract_test_class_from_path(test_path: str) -> str | None:
    """Extract test class name from test path like 'tests/foo.py::TestClass::test_method'"""
    if TEST_SEPARATOR not in test_path:
        return None

    # Split by :: and take up to the test class (not individual test method)
    parts = test_path.split(TEST_SEPARATOR)
    if len(parts) >= MIN_PARTS_FOR_TEST_CLASS:
        # Return path up to and including the test class
        return f"{parts[0]}{TEST_SEPARATOR}{parts[1]}"
    return None


def analyze_test_classes(fpd_data: list[dict[str, Any]]) -> dict[str, list[tuple[str, str, str]]]:
    """Analyze FPD data to find test classes where all tests have passed or xpassed status per language"""
    # Group tests by test class and language, track all outcomes
    test_class_language_outcomes: dict[str, dict[str, dict[str, list[tuple[str, str]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )

    for test_group in fpd_data:
        language = test_group.get("language", "")
        scenario = test_group.get("scenario", "")
        environment = test_group.get("environment", "")
        variant = test_group.get("variant", DEFAULT_VARIANT)  # Default variant is '*'

        # Create a key for this specific environment (language is handled separately now)
        env_key = f"{scenario}_{environment}" if environment else scenario

        for test_run in test_group.get("systemTestRuns", []):
            test_path = test_run.get("testPath", "")
            original_outcome = test_run.get("originalOutcome", "")

            test_class = extract_test_class_from_path(test_path)
            if test_class:
                # Store outcomes grouped by test_class -> language -> env_key
                test_class_language_outcomes[test_class][language][env_key].append((variant, original_outcome))

    # Find test classes where ALL outcomes for a specific language are passed or xpassed
    easy_wins: dict[str, list[tuple[str, str, str]]] = {}

    for test_class, language_data in test_class_language_outcomes.items():
        for language, env_data in language_data.items():
            # Check if ALL outcomes for this test class in this language are xpassed
            all_outcomes_for_language = []
            env_keys_for_language = []

            for env_key, variant_outcomes in env_data.items():
                outcomes = [outcome for variant, outcome in variant_outcomes]
                all_outcomes_for_language.extend(outcomes)
                env_keys_for_language.append(env_key)

            # If ALL outcomes for this language are 'xpassed' or 'passed', it's an easy win for this language
            if all_outcomes_for_language and all(outcome in PASSING_OUTCOMES for outcome in all_outcomes_for_language):
                if test_class not in easy_wins:
                    easy_wins[test_class] = []
                # Add entries with language information included
                for env_key in env_keys_for_language:
                    easy_wins[test_class].append((language, env_key, DEFAULT_VARIANT))  # Include language, env, variant

    return easy_wins


def handle_multiline_yaml(
    lines: list[str], i: int, stripped_line: str, _class_name: str
) -> tuple[bool, str | None, int]:
    """Handle multiline YAML parsing and return (is_multiline, actual_value, lines_to_replace)"""
    status_part = ""
    if ": " in stripped_line:
        status_part = stripped_line.split(": ", 1)[1]

    if status_part in YAML_MULTILINE_INDICATORS:
        # This is multiline YAML, calculate actual lines to replace
        lines_to_replace = calculate_multiline_replacement_count(lines, i, lines[i])

        # Read the next line for the actual value
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            return True, next_line, lines_to_replace
        return True, status_part, lines_to_replace  # Incomplete multiline
    return False, None, 1


def calculate_multiline_replacement_count(lines: list[str], i: int, line: str) -> int:
    """Calculate how many lines need to be replaced for multiline YAML entries"""
    base_indent = len(line) - len(line.lstrip())
    lines_to_replace = 1

    if any(line.strip().endswith(indicator) for indicator in YAML_MULTILINE_INDICATORS):
        # This is multiline YAML, need to remove continuation lines too
        # Look for lines that are indented more than the current line
        j = i + 1
        while j < len(lines):
            next_line = lines[j]
            # Check if this line is a continuation (more indented than base_indent)
            if next_line.strip() == "":
                # Skip empty lines
                j += 1
                continue
            if len(next_line) - len(next_line.lstrip()) > base_indent:
                # This line is more indented than the base, so it's a continuation
                lines_to_replace += 1
                j += 1
            else:
                # This line is not more indented, so we've reached the end of the multiline content
                break

    return lines_to_replace


def get_test_status_info(test_class: str, manifest_file: str) -> TestStatusInfo:
    """Get test status information from manifest file"""
    matches = find_test_class_in_manifest(test_class, manifest_file)

    if not matches:
        return TestStatusInfo()

    # Use the first match (there should typically be only one)
    entry = matches[0]
    return TestStatusInfo.from_manifest_entry(entry)


def find_test_class_in_manifest(test_class: str, manifest_file: str) -> list[ManifestEntry]:
    """Find test class entries in manifest file and return ManifestEntry objects"""
    if TEST_SEPARATOR not in test_class:
        return []

    path_parts = test_class.split("/")
    file_name, class_name = path_parts[-1].split(TEST_SEPARATOR, 1)

    try:
        with open(manifest_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []

    matches = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{class_name}:"):
            # Extract the status after the colon
            if ": " in stripped:
                status_part = stripped.split(": ", 1)[1]

                # Handle YAML multiline indicators
                is_multiline, actual_value, lines_count = handle_multiline_yaml(lines, i, stripped, class_name)
                if is_multiline:
                    if actual_value:
                        first_word = actual_value.split()[0] if actual_value.split() else status_part
                        matches.append(
                            ManifestEntry(
                                line_index=i,
                                status=first_word,
                                is_multiline=True,
                                lines_to_replace=lines_count,
                                original_line=line,
                            )
                        )
                    else:
                        matches.append(
                            ManifestEntry(
                                line_index=i,
                                status=status_part,
                                is_multiline=True,
                                lines_to_replace=1,
                                original_line=line,
                            )
                        )
                else:
                    # Remove any comments for clean status
                    clean_status = status_part.split(" #")[0].split(" (")[0].strip()
                    matches.append(
                        ManifestEntry(
                            line_index=i,
                            status=clean_status,
                            is_multiline=False,
                            lines_to_replace=1,
                            original_line=line,
                        )
                    )
            else:
                # Has variant structure
                matches.append(
                    ManifestEntry(
                        line_index=i,
                        status=STATUS_VARIANT_STRUCTURE,
                        is_multiline=False,
                        lines_to_replace=1,
                        original_line=line,
                    )
                )

    return matches


def update_manifest_file_with_variants(
    test_class: str, language: str, variants: list[str], version: str = STATUS_XPASS
) -> bool:
    """Update manifest file with variant-specific test activation"""
    manifest_file = f"{MANIFEST_DIR}/{language}{MANIFEST_EXTENSION}"

    if not Path(manifest_file).exists():
        print(f"Warning: Manifest file {manifest_file} does not exist")
        return False

    try:
        # Read the original content
        with open(manifest_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Find updatable test entries using the unified parsing function
        matches = find_test_class_in_manifest(test_class, manifest_file)

        # Filter for updatable entries
        updatable_entries = [entry for entry in matches if entry.is_updatable()]

        if updatable_entries:
            # Use the first updatable entry
            entry = updatable_entries[0]
            i = entry.line_index
            line = lines[i]
            path_parts = test_class.split("/")
            file_name, class_name = path_parts[-1].split(TEST_SEPARATOR, 1)

            # Determine if we should use concise format
            use_concise = DEFAULT_VARIANT in variants

            if use_concise:
                # Handle multiline YAML vs direct format
                base_indent = len(line) - len(line.lstrip())
                new_line = " " * base_indent + f"{class_name}: {version}\n"

                # Replace the line(s)
                lines[i : i + entry.lines_to_replace] = [new_line]

                # Write back the file
                with open(manifest_file, "w", encoding="utf-8") as f:
                    f.writelines(lines)

                print(f"Updated {manifest_file}: {test_class} = {version} (was {entry.status})")
                return True
            # Found a missing_feature or bug entry - replace with variant structure
            base_indent = len(line) - len(line.lstrip())
            variant_indent = base_indent + 2

            # Create the new variant structure
            new_lines = []
            new_lines.append(" " * base_indent + f"{class_name}:\n")

            # Add '*': original_status for other variants not in our list
            comment = f" (was {entry.status})" if entry.status != STATUS_MISSING_FEATURE else ""
            new_lines.append(" " * variant_indent + f"'*': {entry.status}{comment}\n")

            # Add specific variants that pass
            for variant in sorted(variants):
                if variant == DEFAULT_VARIANT:
                    continue  # Skip the wildcard, we handle it above
                variant_key = f"'{variant}'"
                new_lines.append(" " * variant_indent + f"{variant_key}: {version}\n")

            # Replace the line(s) with the new structure
            lines[i : i + entry.lines_to_replace] = new_lines

            # Write back the file
            with open(manifest_file, "w", encoding="utf-8") as f:
                f.writelines(lines)

            variants_str = ", ".join(sorted(variants))
            print(
                f"Updated {manifest_file}: {test_class} = {version} for variants: {variants_str} (was {entry.status})"
            )
            return True

        # Check if test class exists with other configurations
        if matches:
            # Test class found but not updatable
            print(
                f"Skipping {manifest_file}: {test_class} already has a configuration "
                f"(no {'/'.join(UPDATABLE_STATUSES)} found)"
            )
            return False

        # Test class not found in manifest
        print(f"Skipping {manifest_file}: {test_class} not found in manifest")
        return False

    except Exception as e:
        print(f"Error updating {manifest_file}: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Activate test classes with all xpass tests")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without making changes")
    parser.add_argument("--language", type=str, help="Only process specific language (e.g., python, java)")
    parser.add_argument(
        "--version",
        type=str,
        default=STATUS_XPASS,
        help=f"Version value to set for activated test classes (default: {STATUS_XPASS})",
    )
    parser.add_argument(
        "--language-versions",
        type=str,
        help=(
            f"Specify different versions per language in format: "
            f"cpp=v1.2.3,python=v2.0.0,java={STATUS_XPASS} "
            f"(languages not specified use --version default)"
        ),
    )
    parser.add_argument(
        "--conservative",
        action="store_true",
        default=False,
        help=(
            f"Only update tests that are marked as {STATUS_MISSING_FEATURE}, "
            f"{STATUS_BUG}, or {STATUS_INCOMPLETE_TEST_APP} in manifest files"
        ),
    )
    parser.add_argument(
        "--force-add", action="store_true", help="Add missing tests even if they don't exist in manifests"
    )
    args = parser.parse_args()

    # Conservative mode is the default unless --force-add is specified
    if not args.force_add:
        args.conservative = True

    # Parse language-specific versions
    language_versions = {}
    if args.language_versions:
        try:
            for pair in args.language_versions.split(","):
                if "=" in pair:
                    lang, version = pair.strip().split("=", 1)
                    language_versions[lang.strip()] = version.strip()
                else:
                    print(f"Warning: Invalid format in language-versions: '{pair}'. Expected format: language=version")
        except Exception as e:
            print(f"Error parsing language-versions: {e}")
            return

    # Function to get version for a specific language
    def get_version_for_language(language: str) -> str:
        return language_versions.get(language, args.version)

    print("Fetching test data from Feature Parity Dashboard...")
    test_results = fetch_fpd_data()
    print(f"Loaded {len(test_results)} test groups")

    print("Analyzing test classes for easy wins...")
    easy_wins = analyze_test_classes(test_results)
    print(f"Found {len(easy_wins)} test classes with all passed/xpassed tests")

    if not easy_wins:
        print("No easy wins found!")
        return

    # Group easy wins by language with variant information
    by_language: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
    for test_class, lang_env_variant_tuples in easy_wins.items():
        for language, _env_key, variant in lang_env_variant_tuples:
            language_id = int(language.split("_")[0]) if "_" in str(language) else int(language)
            language_name = LANGUAGE_MAP.get(language_id, f"unknown_{language_id}")
            if args.language is None or language_name == args.language:
                by_language[language_name].append((test_class, variant))

    # Track tests that are not being updated and the reasons why
    not_updated_tests: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
    # Track tests that are already activated (have version numbers)
    already_activated_tests: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)

    # Categorize all easy wins first (before conservative filtering)
    for language, test_class_variants in by_language.items():
        manifest_file = f"{MANIFEST_DIR}/{language}{MANIFEST_EXTENSION}"
        if Path(manifest_file).exists():
            for test_class, _variant in test_class_variants:
                status_info = get_test_status_info(test_class, manifest_file)
                # Generate reason string once
                if status_info.status is None:
                    reason = MSG_NOT_IN_MANIFEST
                elif status_info.status == STATUS_VARIANT_STRUCTURE:
                    reason = MSG_HAS_VARIANT_STRUCTURE
                else:
                    reason = f"current_status: {status_info.status}"

                if status_info.is_activated:
                    # Test is already activated with a version number
                    already_activated_tests[language].append((test_class, reason))
                elif not status_info.is_updatable:
                    not_updated_tests[language].append((test_class, reason))

    # If conservative mode, filter to only tests that exist in manifests
    if args.conservative:
        filtered_by_language: dict[str, list[tuple[str, str]]] = {}
        for language, test_class_variants in by_language.items():
            manifest_file = f"{MANIFEST_DIR}/{language}{MANIFEST_EXTENSION}"
            if Path(manifest_file).exists():
                filtered_classes = []
                for test_class, _variant in test_class_variants:
                    # Check if this test class exists as missing_feature or bug
                    if get_test_status_info(test_class, manifest_file).is_updatable:
                        filtered_classes.append((test_class, variant))

                if filtered_classes:
                    filtered_by_language[language] = filtered_classes

        by_language.clear()
        by_language.update(filtered_by_language)
        print(
            f"\nConservative mode: Only updating tests marked as "
            f"{STATUS_MISSING_FEATURE}, {STATUS_BUG}, or {STATUS_INCOMPLETE_TEST_APP}"
        )
    # No additional categorization needed in non-conservative mode since we already did it above

    # Show summary
    print("\nEasy wins by language:")
    for language, test_class_variants in sorted(by_language.items()):
        print(f"  {language}: {len(test_class_variants)} test class/variant combinations")

    # Show tests that are xpass but not being updated with reasons
    if not_updated_tests:
        total_not_updated = sum(len(tests) for tests in not_updated_tests.values())
        print(f"\nTests that are passed/xpassed but not being updated ({total_not_updated} total):")
        for language, test_class_reasons in sorted(not_updated_tests.items()):
            print(f"  {language}: {len(test_class_reasons)} tests")

            # Group by reason for better presentation
            by_reason = defaultdict(list)
            for test_class, reason in test_class_reasons:
                by_reason[reason].append(test_class)

            for reason, test_classes in sorted(by_reason.items()):
                print(f"    {reason} ({len(test_classes)} tests):")
                for test_class in sorted(set(test_classes))[:MAX_TESTS_TO_SHOW]:
                    print(f"      - {test_class}")
                if len(set(test_classes)) > MAX_TESTS_TO_SHOW:
                    print(f"      ... and {len(set(test_classes)) - MAX_TESTS_TO_SHOW} more")
    elif not already_activated_tests:
        print("\nAll passed/xpassed tests are being updated.")
    # If we have both not_updated and already_activated, we already showed both sections

    # Show tests that are already activated (summary only)
    if already_activated_tests:
        total_already_activated = sum(len(tests) for tests in already_activated_tests.values())
        print(f"\nTests that are already activated in manifest ({total_already_activated} total):")
        for language, test_class_reasons in sorted(already_activated_tests.items()):
            print(f"  {language}: {len(test_class_reasons)} tests")

    if args.dry_run:
        print("\nDry run - would update the following:")
        for language, test_class_variants in sorted(by_language.items()):
            # Filter out already activated tests from the update list
            manifest_file = f"{MANIFEST_DIR}/{language}{MANIFEST_EXTENSION}"
            tests_to_update = []
            for test_class, _variant in test_class_variants:
                if not Path(manifest_file).exists() or not get_test_status_info(test_class, manifest_file).is_activated:
                    tests_to_update.append((test_class, _variant))

            if tests_to_update:
                print(f"\n{language}.yml:")
                # Group by test class to show variants together
                by_test_class: defaultdict[str, list[str]] = defaultdict(list)
                for test_class, variant in tests_to_update:
                    by_test_class[test_class].append(variant)

                for test_class in sorted(by_test_class.keys()):
                    variants = sorted(set(by_test_class[test_class]))
                    if len(variants) == 1 and variants[0] == DEFAULT_VARIANT:
                        print(f"  {test_class}")
                    else:
                        print(f"  {test_class} (variants: {', '.join(variants)})")
    else:
        print("\nUpdating manifest files...")
        total_updated = 0
        for language, test_class_variants in sorted(by_language.items()):
            # Group by test class to avoid duplicates
            test_variants: dict[str, set[str]] = {}
            for test_class, _variant in test_class_variants:
                if test_class not in test_variants:
                    test_variants[test_class] = set()
                test_variants[test_class].add(variant)

            for test_class in sorted(test_variants.keys()):
                variants = sorted(test_variants[test_class])
                # Update with variant-specific entries
                version_for_language = get_version_for_language(language)
                if update_manifest_file_with_variants(test_class, language, variants, version_for_language):
                    total_updated += 1

        print(f"\nCompleted! Updated {total_updated} test class entries across manifest files.")


if __name__ == "__main__":
    main()
