#!/usr/bin/env python3
"""AWS SSI Registration Tool

This script provides a unified interface for managing AWS SSI configurations:
- Register/update virtual machine compatibility with weblogs
- Register/update scenario configurations
- Register/update weblog configurations

Usage:
    python aws_ssi_registration.py [--vm VM_NAME] [--scenario SCENARIO_NAME] [--weblog WEBLOG_NAME]
    If no arguments are provided, an interactive menu will be shown.
"""

import json
import sys
import argparse
from typing import Any
from collections.abc import Callable
from pathlib import Path

# Get the absolute path to the system-tests directory
SYSTEM_TESTS_DIR = Path(__file__).resolve().parents[3]

# Define paths to required JSON files
VM_JSON_PATH = SYSTEM_TESTS_DIR / "virtual_machine/virtual_machines.json"
AWS_SSI_JSON_PATH = SYSTEM_TESTS_DIR / "scripts/ci_orchestrators/aws_ssi.json"


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


def select_multiple_items(
    items: list[Any],
    prompt_text: str,
    get_display_func: Callable[[Any], str] = lambda x: str(x),
    preselected: list[Any] | None = None,
) -> list[Any]:
    """Helper function for selecting multiple items from a list."""
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
                        print(f"{Colors.RED}Invalid selection: {num + 1}{Colors.ENDC}")
            except ValueError:
                print(f"{Colors.RED}Please enter valid numbers separated by commas.{Colors.ENDC}")

    return [items[i] for i in selected_indices]


def select_language() -> str:
    """Ask the user to select the language for the weblog."""
    languages = ["nodejs", "java", "python", "dotnet", "ruby", "php"]

    print(f"\n{Colors.BOLD}Select the language of the weblog:{Colors.ENDC}")
    for i, lang in enumerate(languages, 1):
        print(f"  {i}. {lang}")

    while True:
        try:
            choice_num = int(input("\nEnter number (1-6): "))
            if 1 <= choice_num <= len(languages):
                return languages[choice_num - 1]
            print(f"{Colors.RED}Please enter a number between 1 and {len(languages)}.{Colors.ENDC}")
        except ValueError:
            print(f"{Colors.RED}Please enter a valid number.{Colors.ENDC}")


# VM Compatibility Functions
def get_vm_details(vm_data: dict, vm_name: str) -> dict:
    """Find VM details by name in the virtual_machines.json data."""
    virtual_machines = vm_data.get("virtual_machines", [])
    for vm in virtual_machines:
        if vm.get("name") == vm_name:
            return vm

    print(f"{Colors.RED}Error: VM with name '{vm_name}' not found.{Colors.ENDC}")
    print(f"{Colors.YELLOW}Available VMs:{Colors.ENDC}")
    for vm in virtual_machines:
        print(f"  - {vm.get('name')}")
    sys.exit(1)


def check_weblog_compatibility(vm_details: dict, weblog_spec: dict, weblog_name: str, language: str) -> bool:
    """Check if a weblog is compatible with a VM based on the rules in aws_ssi.json."""
    # Find the weblog specification in the weblogs_spec section
    for weblog_entry in weblog_spec.get(language, []):
        if weblog_entry.get("name") == weblog_name:
            # Check exact_os_branches - if specified, VM must be in this list
            exact_branches = weblog_entry.get("exact_os_branches", [])
            if exact_branches and vm_details.get("os_branch") not in exact_branches:
                return False

            # Check excluded_os_branches - if VM's os_branch is in this list, it's excluded
            excluded_branches = weblog_entry.get("excluded_os_branches", [])
            if vm_details.get("os_branch") in excluded_branches:
                return False

            # Check excluded_os_names - if VM's name is in this list, it's excluded
            excluded_names = weblog_entry.get("excluded_os_names", [])
            if vm_details.get("name") in excluded_names:
                return False

            # Check excluded_os_types - if VM's os_type is in this list, it's excluded
            excluded_types = weblog_entry.get("excluded_os_types", [])

            # If no exclusions were triggered, the weblog is compatible
            return vm_details.get("os_type") not in excluded_types

    # Weblog not found in specifications - assume incompatible
    return False


def get_compatible_weblogs(vm_details: dict, aws_ssi_data: dict) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Get lists of compatible and incompatible weblogs for a VM."""
    weblog_specs = aws_ssi_data.get("weblogs_spec", {})
    scenario_matrix = aws_ssi_data.get("scenario_matrix", [])

    # Find all unique weblog names in scenario_matrix
    all_weblogs_by_language: dict[str, set[str]] = {}
    for entry in scenario_matrix:
        for weblog_entry in entry.get("weblogs", []):
            for language, weblogs in weblog_entry.items():
                if language not in all_weblogs_by_language:
                    all_weblogs_by_language[language] = set()
                all_weblogs_by_language[language].update(weblogs)

    # Check compatibility for each weblog
    compatible_weblogs: dict[str, list[str]] = {}
    incompatible_weblogs: dict[str, list[str]] = {}

    for language, weblogs in all_weblogs_by_language.items():
        compatible_weblogs[language] = []
        incompatible_weblogs[language] = []

        for weblog in sorted(weblogs):
            if check_weblog_compatibility(vm_details, weblog_specs, weblog, language):
                compatible_weblogs[language].append(weblog)
            else:
                incompatible_weblogs[language].append(weblog)

    return compatible_weblogs, incompatible_weblogs


def update_aws_ssi_json(
    aws_ssi_data: dict, vm_details: dict, weblog: str, language: str, *, make_compatible: bool
) -> dict:
    """Update aws_ssi.json to modify compatibility settings for a weblog and VM."""
    weblog_specs = aws_ssi_data.get("weblogs_spec", {})

    # Find the weblog specification
    for weblog_entry in weblog_specs.get(language, []):
        if weblog_entry.get("name") == weblog:
            if make_compatible:
                # Remove from exact_os_branches if it restricts compatibility
                exact_branches = weblog_entry.get("exact_os_branches", [])
                if exact_branches and vm_details.get("os_branch") not in exact_branches:
                    if "exact_os_branches" not in weblog_entry:
                        weblog_entry["exact_os_branches"] = []
                    weblog_entry["exact_os_branches"].append(vm_details.get("os_branch"))

                # Remove from excluded_os_branches if present
                excluded_branches = weblog_entry.get("excluded_os_branches", [])
                if vm_details.get("os_branch") in excluded_branches:
                    excluded_branches.remove(vm_details.get("os_branch"))
                    if not excluded_branches:
                        weblog_entry.pop("excluded_os_branches", None)
                    else:
                        weblog_entry["excluded_os_branches"] = excluded_branches

                # Remove from excluded_os_names if present
                excluded_names = weblog_entry.get("excluded_os_names", [])
                if vm_details.get("name") in excluded_names:
                    excluded_names.remove(vm_details.get("name"))
                    if not excluded_names:
                        weblog_entry.pop("excluded_os_names", None)
                    else:
                        weblog_entry["excluded_os_names"] = excluded_names

                # Remove from excluded_os_types if present
                excluded_types = weblog_entry.get("excluded_os_types", [])
                if vm_details.get("os_type") in excluded_types:
                    excluded_types.remove(vm_details.get("os_type"))
                    if not excluded_types:
                        weblog_entry.pop("excluded_os_types", None)
                    else:
                        weblog_entry["excluded_os_types"] = excluded_types
            else:  # Make incompatible
                # Add to excluded_os_names
                if "excluded_os_names" not in weblog_entry:
                    weblog_entry["excluded_os_names"] = []
                if vm_details.get("name") not in weblog_entry["excluded_os_names"]:
                    weblog_entry["excluded_os_names"].append(vm_details.get("name"))

            break

    return aws_ssi_data


def print_vm_details(vm_details: dict) -> None:
    """Print VM details in a formatted way."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}VM Details:{Colors.ENDC}")
    print(f"  Name:      {Colors.BOLD}{vm_details.get('name')}{Colors.ENDC}")
    print(f"  OS Type:   {vm_details.get('os_type')}")
    print(f"  OS Branch: {vm_details.get('os_branch')}")
    print(f"  AMI ID:    {vm_details.get('ami_id', 'N/A')}")
    if vm_details.get("disabled"):
        print(f"  Status:    {Colors.RED}Disabled{Colors.ENDC}")
    else:
        print(f"  Status:    {Colors.GREEN}Enabled{Colors.ENDC}")


def handle_vm_compatibility(vm_name: str | None = None) -> None:
    """Handle VM compatibility registration/update."""
    vm_data = load_json_file(str(VM_JSON_PATH))
    aws_ssi_data = load_json_file(str(AWS_SSI_JSON_PATH))

    if vm_name is None:
        # Show list of VMs and let user select one
        virtual_machines = vm_data.get("virtual_machines", [])
        vm_names = [vm.get("name") for vm in virtual_machines]
        selected_vms = select_multiple_items(vm_names, "Select a virtual machine:")
        if not selected_vms:
            print(f"{Colors.YELLOW}No VM selected. Exiting.{Colors.ENDC}")
            return
        vm_name = selected_vms[0]

    vm_details = get_vm_details(vm_data, vm_name)
    print_vm_details(vm_details)

    compatible_weblogs, incompatible_weblogs = get_compatible_weblogs(vm_details, aws_ssi_data)

    print(f"\n{Colors.HEADER}{Colors.BOLD}Current Compatibility Status:{Colors.ENDC}")
    for language in sorted(set(compatible_weblogs.keys()) | set(incompatible_weblogs.keys())):
        print(f"\n{Colors.BLUE}{language}:{Colors.ENDC}")
        if compatible_weblogs.get(language):
            print(f"  {Colors.GREEN}Compatible:{Colors.ENDC}")
            for weblog in compatible_weblogs[language]:
                print(f"    ✓ {weblog}")
        if incompatible_weblogs.get(language):
            print(f"  {Colors.RED}Incompatible:{Colors.ENDC}")
            for weblog in incompatible_weblogs[language]:
                print(f"    ✗ {weblog}")

    # Let user select weblogs to toggle compatibility
    all_weblogs = []
    for language, weblogs in compatible_weblogs.items():
        all_weblogs.extend([(language, weblog, True) for weblog in weblogs])
    for language, weblogs in incompatible_weblogs.items():
        all_weblogs.extend([(language, weblog, False) for weblog in weblogs])

    if not all_weblogs:
        print(f"\n{Colors.YELLOW}No weblogs found in the configuration.{Colors.ENDC}")
        return

    def get_weblog_display(weblog_info: tuple[str, str, bool]) -> str:
        language, weblog, is_compatible = weblog_info
        status = "✓" if is_compatible else "✗"
        return f"{status} {language}: {weblog}"

    selected_weblogs = select_multiple_items(
        all_weblogs,
        "Select weblogs to toggle compatibility (current status shown with ✓/✗):",
        get_weblog_display,
    )

    if not selected_weblogs:
        print(f"{Colors.YELLOW}No changes made.{Colors.ENDC}")
        return

    # Update compatibility for selected weblogs
    for language, weblog, current_status in selected_weblogs:
        aws_ssi_data = update_aws_ssi_json(
            aws_ssi_data, vm_details, weblog, language, make_compatible=not current_status
        )

    save_json_file(str(AWS_SSI_JSON_PATH), aws_ssi_data)


# Scenario Registration Functions
def get_all_scenarios(aws_ssi_data: dict) -> list[str]:
    """Extract all unique scenario names from the AWS SSI configuration."""
    scenarios = set()
    for entry in aws_ssi_data.get("scenario_matrix", []):
        scenarios.update(entry.get("scenarios", []))
    return sorted(scenarios)


def get_all_weblogs_by_language(aws_ssi_data: dict) -> dict[str, list[str]]:
    """Extract all weblogs grouped by language from the AWS SSI configuration."""
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
    """Get all weblogs associated with a specific scenario."""
    scenario_weblogs: dict[str, list[str]] = {}

    for entry in aws_ssi_data.get("scenario_matrix", []):
        if scenario_name in entry.get("scenarios", []):
            for weblog_entry in entry.get("weblogs", []):
                for language, weblogs in weblog_entry.items():
                    if language not in scenario_weblogs:
                        scenario_weblogs[language] = []
                    scenario_weblogs[language].extend(weblogs)

    return scenario_weblogs


def update_scenario_in_matrix(
    aws_ssi_data: dict, scenario_name: str, selected_weblogs_by_language: dict[str, list[str]]
) -> dict:
    """Update the scenario_matrix section of the AWS SSI configuration."""
    scenario_matrix = aws_ssi_data.get("scenario_matrix", [])

    # Remove existing scenario entry if found
    entry_index = -1
    for i, entry in enumerate(scenario_matrix):
        if scenario_name in entry.get("scenarios", []) and len(entry.get("scenarios", [])) == 1:
            entry_index = i
            break

    # Create a new weblog entry for the selected weblogs
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


def handle_scenario_registration(scenario_name: str | None = None) -> None:
    """Handle scenario registration/update."""
    aws_ssi_data = load_json_file(str(AWS_SSI_JSON_PATH))

    if scenario_name is None:
        # Show list of scenarios and let user select one
        scenarios = get_all_scenarios(aws_ssi_data)
        selected_scenarios = select_multiple_items(scenarios, "Select a scenario:")
        if not selected_scenarios:
            print(f"{Colors.YELLOW}No scenario selected. Exiting.{Colors.ENDC}")
            return
        scenario_name = selected_scenarios[0]

    # Get current weblogs for this scenario
    current_weblogs = get_scenario_weblogs(aws_ssi_data, scenario_name)

    # Get all available weblogs by language
    all_weblogs = get_all_weblogs_by_language(aws_ssi_data)

    # Let user select weblogs for each language
    selected_weblogs_by_language: dict[str, list[str]] = {}
    for language, weblogs in all_weblogs.items():
        preselected = current_weblogs.get(language, [])
        selected = select_multiple_items(
            weblogs,
            f"Select weblogs for {language}:",
            preselected=preselected,
        )
        if selected:
            selected_weblogs_by_language[language] = selected

    # Update the configuration
    aws_ssi_data = update_scenario_in_matrix(aws_ssi_data, scenario_name, selected_weblogs_by_language)
    save_json_file(str(AWS_SSI_JSON_PATH), aws_ssi_data)

    # Print the final configuration
    print_scenario_info(scenario_name, selected_weblogs_by_language)


# Weblog Registration Functions
def get_all_virtual_machines(vm_data: dict) -> list[dict]:
    """Get all virtual machines that are not disabled."""
    return [vm for vm in vm_data.get("virtual_machines", []) if not vm.get("disabled", False)]


def get_weblog_info(aws_ssi_data: dict, weblog_name: str, language: str) -> tuple[list[str], dict]:
    """Get information about an existing weblog."""
    associated_scenarios = []
    weblog_spec = {}

    # Find scenarios associated with this weblog
    for entry in aws_ssi_data.get("scenario_matrix", []):
        for weblog_entry in entry.get("weblogs", []):
            if language in weblog_entry and weblog_name in weblog_entry.get(language, []):
                associated_scenarios.extend(entry.get("scenarios", []))

    # Find weblog specification in weblogs_spec
    weblogs_spec = aws_ssi_data.get("weblogs_spec", {}).get(language, [])
    for spec in weblogs_spec:
        if spec.get("name") == weblog_name:
            weblog_spec = spec
            break

    return associated_scenarios, weblog_spec


def is_vm_compatible_with_weblog(vm: dict, weblog_spec: dict) -> bool:
    """Check if a VM is compatible with a weblog based on the weblog's specification."""
    # Check exact_os_branches - if specified, VM must be in this list
    exact_branches = weblog_spec.get("exact_os_branches", [])
    if exact_branches and vm.get("os_branch") not in exact_branches:
        return False

    # Check excluded_os_branches - if VM's os_branch is in this list, it's excluded
    excluded_branches = weblog_spec.get("excluded_os_branches", [])
    if vm.get("os_branch") in excluded_branches:
        return False

    # Check excluded_os_names - if VM's name is in this list, it's excluded
    excluded_names = weblog_spec.get("excluded_os_names", [])
    if vm.get("name") in excluded_names:
        return False

    # Check excluded_os_types - if VM's os_type is in this list, it's excluded
    excluded_types = weblog_spec.get("excluded_os_types", [])

    # Return True if the VM is compatible (os_type not in excluded_types)
    return vm.get("os_type") not in excluded_types


def update_scenario_matrix(aws_ssi_data: dict, weblog_name: str, language: str, selected_scenarios: list[str]) -> dict:
    """Update the scenario_matrix section of the AWS SSI configuration."""
    scenario_matrix = aws_ssi_data.get("scenario_matrix", [])

    # First, remove the weblog from any existing scenario entries
    for entry in scenario_matrix:
        for weblog_entry in entry.get("weblogs", []):
            if language in weblog_entry and weblog_name in weblog_entry.get(language, []):
                weblog_entry[language].remove(weblog_name)
                # If this was the only weblog for this language, remove the language entry
                if not weblog_entry[language]:
                    weblog_entry.pop(language)
                # If the weblog entry is now empty, make it an empty list to be cleaned up later
                if not weblog_entry:
                    entry["weblogs"] = [we for we in entry["weblogs"] if we]

    # Then, add the weblog to the selected scenarios
    for scenario in selected_scenarios:
        # Try to find an existing entry for this scenario
        entry_found = False
        for entry in scenario_matrix:
            if scenario in entry.get("scenarios", []):
                entry_found = True
                # Add the weblog to this entry
                for weblog_entry in entry.get("weblogs", []):
                    if language in weblog_entry:
                        if weblog_name not in weblog_entry[language]:
                            weblog_entry[language].append(weblog_name)
                        break
                else:
                    # No existing weblog entry for this language, create one
                    entry["weblogs"].append({language: [weblog_name]})
                break

        if not entry_found:
            # Create a new entry for this scenario
            scenario_matrix.append(
                {
                    "scenarios": [scenario],
                    "weblogs": [{language: [weblog_name]}],
                }
            )

    return aws_ssi_data


def update_weblog_spec(
    aws_ssi_data: dict, weblog_name: str, language: str, compatible_vms: list[dict], all_vms: list[dict]
) -> dict:
    """Update the weblogs_spec section of the AWS SSI configuration."""
    weblogs_spec = aws_ssi_data.get("weblogs_spec", {})
    if language not in weblogs_spec:
        weblogs_spec[language] = []

    # Find existing weblog specification
    weblog_spec = None
    for spec in weblogs_spec[language]:
        if spec.get("name") == weblog_name:
            weblog_spec = spec
            break

    if weblog_spec is None:
        # Create new weblog specification
        weblog_spec = {"name": weblog_name}
        weblogs_spec[language].append(weblog_spec)

    # Update compatibility settings
    excluded_os_branches = []
    excluded_os_names = []
    excluded_os_types = []
    exact_os_branches = []

    for vm in all_vms:
        if vm not in compatible_vms:
            # Add to excluded lists
            if vm.get("os_branch") not in excluded_os_branches:
                excluded_os_branches.append(vm.get("os_branch"))
            if vm.get("name") not in excluded_os_names:
                excluded_os_names.append(vm.get("name"))
            if vm.get("os_type") not in excluded_os_types:
                excluded_os_types.append(vm.get("os_type"))
        # Add to exact_os_branches if not already there
        elif vm.get("os_branch") not in exact_os_branches:
            exact_os_branches.append(vm.get("os_branch"))

    # Update the weblog specification
    if excluded_os_branches:
        weblog_spec["excluded_os_branches"] = excluded_os_branches
    else:
        weblog_spec.pop("excluded_os_branches", None)

    if excluded_os_names:
        weblog_spec["excluded_os_names"] = excluded_os_names
    else:
        weblog_spec.pop("excluded_os_names", None)

    if excluded_os_types:
        weblog_spec["excluded_os_types"] = excluded_os_types
    else:
        weblog_spec.pop("excluded_os_types", None)

    if exact_os_branches:
        weblog_spec["exact_os_branches"] = exact_os_branches
    else:
        weblog_spec.pop("exact_os_branches", None)

    return aws_ssi_data


def print_weblog_info(
    weblog_name: str, language: str, scenarios: list[str], compatible_vms: list[dict], incompatible_vms: list[dict]
) -> None:
    """Print information about the weblog configuration."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}Weblog Configuration:{Colors.ENDC}")
    print(f"  Name:     {Colors.BOLD}{weblog_name}{Colors.ENDC}")
    print(f"  Language: {Colors.BOLD}{language}{Colors.ENDC}")

    print(f"\n{Colors.GREEN}Associated Scenarios:{Colors.ENDC}")
    if scenarios:
        for scenario in sorted(scenarios):
            print(f"  - {scenario}")
    else:
        print(f"  {Colors.YELLOW}No scenarios associated with this weblog.{Colors.ENDC}")

    print(f"\n{Colors.GREEN}Compatible VMs:{Colors.ENDC}")
    if compatible_vms:
        for vm in sorted(compatible_vms, key=lambda x: x.get("name", "")):
            print(f"  ✓ {vm.get('name')} ({vm.get('os_type')} - {vm.get('os_branch')})")
    else:
        print(f"  {Colors.YELLOW}No compatible VMs.{Colors.ENDC}")

    print(f"\n{Colors.RED}Incompatible VMs:{Colors.ENDC}")
    if incompatible_vms:
        for vm in sorted(incompatible_vms, key=lambda x: x.get("name", "")):
            print(f"  ✗ {vm.get('name')} ({vm.get('os_type')} - {vm.get('os_branch')})")
    else:
        print(f"  {Colors.GREEN}No incompatible VMs.{Colors.ENDC}")


def handle_weblog_registration(weblog_name: str | None = None) -> None:
    """Handle weblog registration/update."""
    vm_data = load_json_file(str(VM_JSON_PATH))
    aws_ssi_data = load_json_file(str(AWS_SSI_JSON_PATH))

    if weblog_name is None:
        # Get all weblogs by language
        all_weblogs = get_all_weblogs_by_language(aws_ssi_data)

        # Let user select language first
        language = select_language()

        # Then select weblog from that language
        weblogs = all_weblogs.get(language, [])
        if not weblogs:
            print(f"{Colors.YELLOW}No weblogs found for {language}.{Colors.ENDC}")
            return

        selected_weblogs = select_multiple_items(weblogs, f"Select a weblog for {language}:")
        if not selected_weblogs:
            print(f"{Colors.YELLOW}No weblog selected. Exiting.{Colors.ENDC}")
            return
        weblog_name = selected_weblogs[0]
    else:
        # If weblog name is provided, ask for language
        language = select_language()

    # Get current configuration
    current_scenarios, weblog_spec = get_weblog_info(aws_ssi_data, weblog_name, language)

    # Get all available scenarios
    all_scenarios = get_all_scenarios(aws_ssi_data)

    # Let user select scenarios
    selected_scenarios = select_multiple_items(
        all_scenarios,
        "Select scenarios for this weblog:",
        preselected=current_scenarios,
    )

    # Get all VMs
    all_vms = get_all_virtual_machines(vm_data)

    # Let user select compatible VMs
    def get_vm_display(vm: dict) -> str:
        return f"{vm.get('name')} ({vm.get('os_type')} - {vm.get('os_branch')})"

    preselected_vms = [vm for vm in all_vms if is_vm_compatible_with_weblog(vm, weblog_spec)]
    compatible_vms = select_multiple_items(
        all_vms,
        "Select compatible VMs:",
        get_vm_display,
        preselected=preselected_vms,
    )

    # Update the configuration
    aws_ssi_data = update_scenario_matrix(aws_ssi_data, weblog_name, language, selected_scenarios)
    aws_ssi_data = update_weblog_spec(aws_ssi_data, weblog_name, language, compatible_vms, all_vms)
    save_json_file(str(AWS_SSI_JSON_PATH), aws_ssi_data)

    # Print the final configuration
    incompatible_vms = [vm for vm in all_vms if vm not in compatible_vms]
    print_weblog_info(weblog_name, language, selected_scenarios, compatible_vms, incompatible_vms)


def show_interactive_menu() -> None:
    """Show the interactive menu for selecting an operation."""
    # Menu option constants
    menu_vm_compatibility = 1
    menu_scenario = 2
    menu_weblog = 3
    menu_options = 4  # Number of menu options

    print(f"\n{Colors.HEADER}{Colors.BOLD}AWS SSI Registration Tool{Colors.ENDC}")
    print("Select an operation:")
    print("  1. Register/Update VM Compatibility")
    print("  2. Register/Update Scenario")
    print("  3. Register/Update Weblog")
    print("  4. Exit")

    while True:
        try:
            choice = int(input(f"\nEnter your choice (1-{menu_options}): "))
            if 1 <= choice <= menu_options:
                break
            print(f"{Colors.RED}Please enter a number between 1 and {menu_options}.{Colors.ENDC}")
        except ValueError:
            print(f"{Colors.RED}Please enter a valid number.{Colors.ENDC}")

    if choice == menu_vm_compatibility:
        handle_vm_compatibility()
    elif choice == menu_scenario:
        handle_scenario_registration()
    elif choice == menu_weblog:
        handle_weblog_registration()
    else:
        print(f"{Colors.YELLOW}Exiting.{Colors.ENDC}")
        sys.exit(0)


def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="AWS SSI Registration Tool")
    parser.add_argument("--vm", help="Virtual machine name for compatibility check")
    parser.add_argument("--scenario", help="Scenario name for registration")
    parser.add_argument("--weblog", help="Weblog name for registration")

    args = parser.parse_args()

    if args.vm:
        handle_vm_compatibility(args.vm)
    elif args.scenario:
        handle_scenario_registration(args.scenario)
    elif args.weblog:
        handle_weblog_registration(args.weblog)
    else:
        show_interactive_menu()


if __name__ == "__main__":
    main()
