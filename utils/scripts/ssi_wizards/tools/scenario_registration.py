#!/usr/bin/env python3
"""Scenario Registration Tool for AWS SSI

This script allows users to register a new scenario or update an existing one in the AWS SSI configuration.
It provides interactive selection of weblogs to associate with the scenario.
"""

import json
import sys
from typing import Any
from collections.abc import Callable
from pathlib import Path

# Get the absolute path to the system-tests directory
SYSTEM_TESTS_DIR = Path(__file__).resolve().parents[3]

# Define path to required JSON file
AWS_SSI_JSON_PATH = SYSTEM_TESTS_DIR / "utils/scripts/ci_orchestrators/aws_ssi.json"


# Terminal colors for better readability
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def load_json_file(file_path: str) -> dict:
    """Load a JSON file and return its contents as a dictionary."""
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"{Colors.RED}Error: File {file_path} not found.{Colors.ENDC}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"{Colors.RED}Error: File {file_path} is not valid JSON.{Colors.ENDC}")
        sys.exit(1)


def save_json_file(file_path: str, data: dict) -> None:
    """Save data as JSON to the specified file."""
    try:
        # Create backup first
        backup_path = f"{file_path}.bak"
        with open(file_path, "r") as src, open(backup_path, "w") as backup:
            backup.write(src.read())

        # Now write the updated data
        with open(file_path, "w") as file:
            json.dump(data, file, indent=4)

        print(f"{Colors.GREEN}File updated successfully. Backup saved to {backup_path}{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.RED}Error saving file: {e!s}{Colors.ENDC}")
        sys.exit(1)


def get_all_weblogs_by_language(aws_ssi_data: dict) -> dict[str, list[str]]:
    """Extract all weblogs grouped by language from the AWS SSI configuration.

    Args:
        aws_ssi_data: The AWS SSI configuration data

    Returns:
        Dictionary with language as key and list of weblog names as value

    """
    all_weblogs: dict[str, set[str]] = {}

    # Extract weblogs from scenario_matrix
    for entry in aws_ssi_data.get("scenario_matrix", []):
        for weblog_entry in entry.get("weblogs", []):
            for language, weblogs in weblog_entry.items():
                if language not in all_weblogs:
                    all_weblogs[language] = set()
                all_weblogs[language].update(weblogs)

    # Extract weblogs from weblogs_spec
    for language, weblogs_spec in aws_ssi_data.get("weblogs_spec", {}).items():
        if language not in all_weblogs:
            all_weblogs[language] = set()
        for weblog_spec in weblogs_spec:
            all_weblogs[language].add(weblog_spec.get("name"))

    # Convert sets to sorted lists
    return {lang: sorted(weblogs) for lang, weblogs in all_weblogs.items()}


def get_scenario_weblogs(aws_ssi_data: dict, scenario_name: str) -> dict[str, list[str]]:
    """Get all weblogs associated with a specific scenario.

    Args:
        aws_ssi_data: The AWS SSI configuration data
        scenario_name: Name of the scenario to check

    Returns:
        Dictionary with language as key and list of weblog names as value

    """
    scenario_weblogs: dict[str, list[str]] = {}

    for entry in aws_ssi_data.get("scenario_matrix", []):
        if scenario_name in entry.get("scenarios", []):
            for weblog_entry in entry.get("weblogs", []):
                for language, weblogs in weblog_entry.items():
                    if language not in scenario_weblogs:
                        scenario_weblogs[language] = []
                    scenario_weblogs[language].extend(weblogs)

    return scenario_weblogs


def select_multiple_items(
    items: list[Any],
    prompt_text: str,
    get_display_func: Callable[[Any], str] = lambda x: str(x),
    preselected: list[Any] | None = None,
) -> list[Any]:
    """Helper function for selecting multiple items from a list.

    Args:
        items: List of items to choose from
        prompt_text: Text to display before the list
        get_display_func: Function to get display string for each item
        preselected: List of items that should be preselected

    Returns:
        List of selected items

    """
    if preselected is None:
        preselected = []

    selected_indices = [i for i, item in enumerate(items) if item in preselected]

    while True:
        print(f"\n{Colors.BOLD}{prompt_text}{Colors.ENDC}")
        print("  (Enter numbers separated by commas, 'all' to select all, or 'done' when finished)")

        # Display all items with selection status
        for i, item in enumerate(items):
            already_selected = "✓ " if i in selected_indices else "  "
            print(f"  {already_selected}{i + 1}. {get_display_func(item)}")

        choice = input("\nEnter selection: ").strip().lower()

        if choice == "done":
            break
        if choice == "all":
            selected_indices = list(range(len(items)))
        else:
            try:
                # Parse comma-separated numbers
                for num_str in choice.split(","):
                    num = int(num_str.strip()) - 1  # Convert to 0-indexed
                    if 0 <= num < len(items):
                        if num not in selected_indices:
                            selected_indices.append(num)
                        else:
                            selected_indices.remove(num)  # Toggle selection
                    else:
                        print(f"{Colors.RED}Invalid selection: {num+1}{Colors.ENDC}")
            except ValueError:
                print(f"{Colors.RED}Please enter valid numbers separated by commas.{Colors.ENDC}")

    return [items[i] for i in selected_indices]


def update_scenario_in_matrix(
    aws_ssi_data: dict, scenario_name: str, selected_weblogs_by_language: dict[str, list[str]]
) -> dict:
    """Update the scenario_matrix section of the AWS SSI configuration.

    Args:
        aws_ssi_data: The AWS SSI configuration data
        scenario_name: Name of the scenario to add/update
        selected_weblogs_by_language: Dictionary with language as key and list of selected weblog names as value

    Returns:
        Updated AWS SSI configuration

    """
    scenario_matrix = aws_ssi_data.get("scenario_matrix", [])

    # Remove existing scenario entry if found
    entry_index = -1
    for i, entry in enumerate(scenario_matrix):
        if scenario_name in entry.get("scenarios", []) and len(entry.get("scenarios", [])) == 1:
            entry_index = i
            break

    # Create a new weblog entry for the selected weblogs using dictionary comprehension
    weblog_entry = {language: weblogs for language, weblogs in selected_weblogs_by_language.items() if weblogs}

    # Create the new scenario entry
    new_entry = {"scenarios": [scenario_name], "weblogs": [weblog_entry] if weblog_entry else []}

    # Replace existing entry or add a new one
    if entry_index >= 0:
        scenario_matrix[entry_index] = new_entry
    else:
        scenario_matrix.append(new_entry)

    aws_ssi_data["scenario_matrix"] = scenario_matrix
    return aws_ssi_data


def print_scenario_info(scenario_name: str, selected_weblogs_by_language: dict[str, list[str]]) -> None:
    """Print information about the scenario configuration."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}Scenario Configuration:{Colors.ENDC}")
    print(f"  Scenario Name: {Colors.BOLD}{scenario_name}{Colors.ENDC}")

    print(f"\n{Colors.GREEN}Selected Weblogs:{Colors.ENDC}")
    has_weblogs = False
    for language, weblogs in selected_weblogs_by_language.items():
        if weblogs:
            has_weblogs = True
            print(f"  {Colors.BLUE}{language}:{Colors.ENDC}")
            for weblog in sorted(weblogs):
                print(f"    - {weblog}")

    if not has_weblogs:
        print(f"  {Colors.YELLOW}No weblogs selected for this scenario.{Colors.ENDC}")


def check_scenario_in_class(scenario_name: str) -> bool:
    """Check if the scenario is defined in the _Scenarios class in __init__.py.
    This is a simple check that just warns the user but doesn't prevent registration.

    Args:
        scenario_name: Name of the scenario to check

    Returns:
        True if found, False otherwise

    """
    init_py_path = SYSTEM_TESTS_DIR / "utils/_context/_scenarios/__init__.py"
    if not init_py_path.exists():
        print(f"{Colors.YELLOW}Warning: Could not find scenarios definition file. Skipping check.{Colors.ENDC}")
        return False

    try:
        with open(init_py_path, "r") as f:
            content = f.read()
            # Look for the scenario name in the file
            return f'"{scenario_name}"' in content or f"'{scenario_name}'" in content
    except Exception as e:
        print(f"{Colors.YELLOW}Warning: Error checking scenario definition: {e!s}{Colors.ENDC}")
        return False


def main() -> None:
    # Check if a scenario name was provided
    expected_args_count = 2
    if len(sys.argv) != expected_args_count:
        print(f"Usage: {sys.argv[0]} <scenario_name>")
        print(f"Example: {sys.argv[0]} CUSTOM_AUTO_INJECTION")
        sys.exit(1)

    scenario_name = sys.argv[1].upper()  # Convert to uppercase as per convention

    # Load JSON data
    print(f"{Colors.BLUE}Loading AWS SSI configuration...{Colors.ENDC}")
    aws_ssi_data = load_json_file(str(AWS_SSI_JSON_PATH))

    # Check if the scenario exists in the _Scenarios class
    scenario_defined = check_scenario_in_class(scenario_name)
    if not scenario_defined:
        print(
            f"{Colors.YELLOW}Warning: The scenario '{scenario_name}' does not appear to be defined "
            f"in the _Scenarios class.{Colors.ENDC}"
        )
        print(
            f"{Colors.YELLOW}You should define it in utils/_context/_scenarios/__init__.py before "
            f"using it.{Colors.ENDC}"
        )

        print(f"\n{Colors.YELLOW}Do you want to continue anyway? (y/n){Colors.ENDC}")
        if input().lower() != "y":
            print(f"{Colors.BLUE}Script execution cancelled.{Colors.ENDC}")
            sys.exit(0)

    # Get all weblogs by language
    all_weblogs_by_language = get_all_weblogs_by_language(aws_ssi_data)

    # Get weblogs currently associated with the scenario
    current_weblogs_by_language = get_scenario_weblogs(aws_ssi_data, scenario_name)

    # Check if the scenario already exists
    is_existing_scenario = any(
        scenario_name in entry.get("scenarios", []) for entry in aws_ssi_data.get("scenario_matrix", [])
    )

    if is_existing_scenario:
        print(f"\n{Colors.YELLOW}Scenario '{scenario_name}' already exists in the configuration.{Colors.ENDC}")
        print(f"{Colors.YELLOW}You can now update its associated weblogs.{Colors.ENDC}")
    else:
        print(f"\n{Colors.GREEN}Registering new scenario '{scenario_name}'.{Colors.ENDC}")

    # Initialize selected weblogs for each language
    selected_weblogs_by_language = {}

    # For each language, ask the user to select weblogs
    for language, weblogs in sorted(all_weblogs_by_language.items()):
        preselected = current_weblogs_by_language.get(language, [])
        selected = select_multiple_items(
            weblogs, f"Select {language} weblogs for scenario '{scenario_name}':", preselected=preselected
        )

        if selected:
            selected_weblogs_by_language[language] = selected

    # Display the current configuration
    print_scenario_info(scenario_name, selected_weblogs_by_language)

    # Confirm the changes
    print(f"\n{Colors.BOLD}Summary of changes to be made:{Colors.ENDC}")
    print(f"  - {'Update' if is_existing_scenario else 'Create'} scenario '{scenario_name}'")
    weblogs_count = sum(len(weblogs) for weblogs in selected_weblogs_by_language.values())
    print(f"  - Associate with {weblogs_count} weblog(s) across {len(selected_weblogs_by_language)} language(s)")

    print(f"\n{Colors.YELLOW}Do you want to save these changes to aws_ssi.json? (y/n){Colors.ENDC}")
    if input().lower() != "y":
        print(f"{Colors.YELLOW}Changes were not saved.{Colors.ENDC}")
        sys.exit(0)

    # Update the configuration
    aws_ssi_data = update_scenario_in_matrix(aws_ssi_data, scenario_name, selected_weblogs_by_language)

    # Save the changes
    save_json_file(str(AWS_SSI_JSON_PATH), aws_ssi_data)

    print(
        f"\n{Colors.GREEN}{Colors.BOLD}Scenario {scenario_name} has been successfully "
        f"{'updated' if is_existing_scenario else 'registered'}.{Colors.ENDC}"
    )
    print(f"{Colors.GREEN}The changes have been saved to aws_ssi.json.{Colors.ENDC}")

    # Provide next steps
    if not scenario_defined:
        print(
            f"\n{Colors.YELLOW}Remember to define this scenario in utils/_context/_scenarios/__init__.py{Colors.ENDC}"
        )
        print(f"{Colors.YELLOW}Example:{Colors.ENDC}")
        print(f"""
{scenario_name.lower()} = InstallerAutoInjectionScenario(
    "{scenario_name}",
    "Description of your scenario",
    # Optional: Use a custom provision
    # vm_provision="custom-provision-name",
    # Optional: Set environment variables for agent
    # agent_env={{ "KEY": "VALUE" }},
    # Optional: Set environment variables for application
    # app_env={{ "KEY": "VALUE" }},
    scenario_groups=[scenario_groups.onboarding],
    github_workflow="aws_ssi",
)
        """)


if __name__ == "__main__":
    main()
