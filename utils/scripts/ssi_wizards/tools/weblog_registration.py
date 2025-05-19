#!/usr/bin/env python3
"""
Weblog Registration Tool for AWS SSI

This script allows users to register or update a weblog in the AWS SSI configuration.
It provides interactive selection of scenarios and virtual machines to associate with the weblog.
"""

import json
import os
import sys
from typing import Dict, List, Set, Tuple, Any, Optional

# Get the absolute path to the system-tests directory
SYSTEM_TESTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))

# Define paths to required JSON files
VM_JSON_PATH = os.path.join(SYSTEM_TESTS_DIR, "utils/virtual_machine/virtual_machines.json")
AWS_SSI_JSON_PATH = os.path.join(SYSTEM_TESTS_DIR, "utils/scripts/ci_orchestrators/aws_ssi.json")

# Terminal colors for better readability
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def load_json_file(file_path: str) -> dict:
    """Load a JSON file and return its contents as a dictionary."""
    try:
        with open(file_path, 'r') as file:
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
        with open(file_path, 'r') as src, open(backup_path, 'w') as backup:
            backup.write(src.read())
            
        # Now write the updated data
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)
            
        print(f"{Colors.GREEN}File updated successfully. Backup saved to {backup_path}{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.RED}Error saving file: {str(e)}{Colors.ENDC}")
        sys.exit(1)


def get_all_scenarios(aws_ssi_data: dict) -> List[str]:
    """Extract all unique scenario names from the AWS SSI configuration."""
    scenarios = set()
    for entry in aws_ssi_data.get("scenario_matrix", []):
        scenarios.update(entry.get("scenarios", []))
    return sorted(list(scenarios))


def get_all_virtual_machines(vm_data: dict) -> List[dict]:
    """Get all virtual machines that are not disabled."""
    return [vm for vm in vm_data.get("virtual_machines", []) if not vm.get("disabled", False)]


def get_weblog_info(aws_ssi_data: dict, weblog_name: str, language: str) -> Tuple[List[str], dict]:
    """
    Get information about an existing weblog.
    
    Args:
        aws_ssi_data: The AWS SSI configuration data
        weblog_name: The name of the weblog
        language: The language of the weblog
    
    Returns:
        Tuple containing:
        - List of scenarios associated with the weblog
        - Dictionary with weblog specifications
    """
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
    """
    Check if a VM is compatible with a weblog based on the weblog's specification.
    
    Args:
        vm: Dictionary with VM details
        weblog_spec: Dictionary with weblog specifications
    
    Returns:
        True if compatible, False otherwise
    """
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
    if vm.get("os_type") in excluded_types:
        return False
    
    # If no exclusions were triggered, the VM is compatible
    return True


def select_multiple_items(items: List[Any], prompt_text: str, 
                          get_display_func=lambda x: str(x),
                          preselected: List[Any] = None) -> List[Any]:
    """
    Helper function for selecting multiple items from a list.
    
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
        print(f"  (Enter numbers separated by commas, 'all' to select all, or 'done' when finished)")
        
        # Display all items with selection status
        for i, item in enumerate(items):
            already_selected = "✓ " if i in selected_indices else "  "
            print(f"  {already_selected}{i + 1}. {get_display_func(item)}")
        
        choice = input("\nEnter selection: ").strip().lower()
        
        if choice == 'done':
            break
        elif choice == 'all':
            selected_indices = list(range(len(items)))
        else:
            try:
                # Parse comma-separated numbers
                for num in choice.split(','):
                    num = int(num.strip()) - 1  # Convert to 0-indexed
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


def select_language() -> str:
    """Ask the user to select the language for the weblog."""
    languages = ["nodejs", "java", "python", "dotnet", "ruby", "php"]
    
    print(f"\n{Colors.BOLD}Select the language of the weblog:{Colors.ENDC}")
    for i, lang in enumerate(languages, 1):
        print(f"  {i}. {lang}")
    
    while True:
        try:
            choice = int(input("\nEnter number (1-6): "))
            if 1 <= choice <= len(languages):
                return languages[choice - 1]
            print(f"{Colors.RED}Please enter a number between 1 and {len(languages)}.{Colors.ENDC}")
        except ValueError:
            print(f"{Colors.RED}Please enter a valid number.{Colors.ENDC}")


def update_scenario_matrix(aws_ssi_data: dict, weblog_name: str, language: str, 
                           selected_scenarios: List[str]) -> dict:
    """
    Update the scenario_matrix section of the AWS SSI configuration.
    
    Args:
        aws_ssi_data: The AWS SSI configuration data
        weblog_name: Name of the weblog to add/update
        language: Language of the weblog
        selected_scenarios: List of scenarios to associate with the weblog
    
    Returns:
        Updated AWS SSI configuration
    """
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
                found_language = False
                for weblog_entry in entry.get("weblogs", []):
                    if language in weblog_entry:
                        if weblog_name not in weblog_entry[language]:
                            weblog_entry[language].append(weblog_name)
                        found_language = True
                        break
                
                if not found_language:
                    # Add a new language entry
                    entry["weblogs"].append({language: [weblog_name]})
                break
        
        if not entry_found:
            # Create a new entry for this scenario
            scenario_matrix.append({
                "scenarios": [scenario],
                "weblogs": [{language: [weblog_name]}]
            })
    
    # Clean up empty entries
    aws_ssi_data["scenario_matrix"] = [
        entry for entry in scenario_matrix 
        if entry.get("scenarios") and entry.get("weblogs") and any(we for we in entry.get("weblogs", []))
    ]
    
    return aws_ssi_data


def update_weblog_spec(aws_ssi_data: dict, weblog_name: str, language: str, 
                        compatible_vms: List[dict], all_vms: List[dict]) -> dict:
    """
    Update the weblogs_spec section of the AWS SSI configuration.
    
    Args:
        aws_ssi_data: The AWS SSI configuration data
        weblog_name: Name of the weblog to add/update
        language: Language of the weblog
        compatible_vms: List of VMs that should be compatible with this weblog
        all_vms: List of all available VMs
    
    Returns:
        Updated AWS SSI configuration
    """
    if "weblogs_spec" not in aws_ssi_data:
        aws_ssi_data["weblogs_spec"] = {}
    
    if language not in aws_ssi_data["weblogs_spec"]:
        aws_ssi_data["weblogs_spec"][language] = []
    
    # Find existing weblog spec or create a new one
    weblog_spec = None
    for spec in aws_ssi_data["weblogs_spec"][language]:
        if spec.get("name") == weblog_name:
            weblog_spec = spec
            break
    
    if weblog_spec is None:
        weblog_spec = {"name": weblog_name}
        aws_ssi_data["weblogs_spec"][language].append(weblog_spec)
    
    # Get lists of branches, names and types for compatible and incompatible VMs
    compatible_branches = set(vm.get("os_branch") for vm in compatible_vms)
    compatible_names = set(vm.get("name") for vm in compatible_vms)
    compatible_types = set(vm.get("os_type") for vm in compatible_vms)
    
    all_branches = set(vm.get("os_branch") for vm in all_vms)
    all_names = set(vm.get("name") for vm in all_vms)
    all_types = set(vm.get("os_type") for vm in all_vms)
    
    # Determine the most efficient way to represent compatibility
    # If the weblog is compatible with all VMs, we don't need any restrictions
    if len(compatible_vms) == len(all_vms):
        # Remove all restrictions
        weblog_spec.pop("exact_os_branches", None)
        weblog_spec.pop("excluded_os_branches", None)
        weblog_spec.pop("excluded_os_names", None)
        weblog_spec.pop("excluded_os_types", None)
    
    # If the weblog is compatible with only specific OS branches
    elif len(compatible_branches) <= len(all_branches) / 2:
        weblog_spec["exact_os_branches"] = sorted(list(compatible_branches))
        weblog_spec.pop("excluded_os_branches", None)
        weblog_spec.pop("excluded_os_names", None)
        weblog_spec.pop("excluded_os_types", None)
    
    # Otherwise, specify which VMs are excluded
    else:
        weblog_spec.pop("exact_os_branches", None)
        
        # Exclude branches
        incompatible_branches = all_branches - compatible_branches
        if incompatible_branches:
            weblog_spec["excluded_os_branches"] = sorted(list(incompatible_branches))
        else:
            weblog_spec.pop("excluded_os_branches", None)
        
        # Exclude VM names (for specific exclusions)
        incompatible_names = all_names - compatible_names
        incompatible_names = {name for name in incompatible_names 
                              if not any(vm.get("os_branch") in incompatible_branches 
                                        for vm in all_vms if vm.get("name") == name)}
        if incompatible_names:
            weblog_spec["excluded_os_names"] = sorted(list(incompatible_names))
        else:
            weblog_spec.pop("excluded_os_names", None)
        
        # Exclude OS types
        incompatible_types = all_types - compatible_types
        if incompatible_types:
            weblog_spec["excluded_os_types"] = sorted(list(incompatible_types))
        else:
            weblog_spec.pop("excluded_os_types", None)
    
    return aws_ssi_data


def print_weblog_info(weblog_name: str, language: str, scenarios: List[str], 
                      compatible_vms: List[dict], incompatible_vms: List[dict]) -> None:
    """Print information about the weblog configuration."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}Weblog Configuration:{Colors.ENDC}")
    print(f"  Name:      {Colors.BOLD}{weblog_name}{Colors.ENDC}")
    print(f"  Language:  {language}")
    
    print(f"\n{Colors.GREEN}Associated Scenarios:{Colors.ENDC}")
    if scenarios:
        for scenario in sorted(scenarios):
            print(f"  - {scenario}")
    else:
        print(f"  {Colors.YELLOW}No scenarios associated with this weblog.{Colors.ENDC}")
    
    print(f"\n{Colors.GREEN}Compatible Virtual Machines ({len(compatible_vms)}):{Colors.ENDC}")
    if compatible_vms:
        for vm in sorted(compatible_vms, key=lambda x: x.get("name", "")):
            print(f"  - {vm.get('name')} ({vm.get('os_branch')})")
    else:
        print(f"  {Colors.YELLOW}No compatible virtual machines.{Colors.ENDC}")
    
    print(f"\n{Colors.RED}Incompatible Virtual Machines ({len(incompatible_vms)}):{Colors.ENDC}")
    if incompatible_vms:
        for vm in sorted(incompatible_vms, key=lambda x: x.get("name", "")):
            print(f"  - {vm.get('name')} ({vm.get('os_branch')})")
    else:
        print(f"  {Colors.GREEN}All virtual machines are compatible.{Colors.ENDC}")


def main():
    # Check if a weblog name was provided
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <weblog_name>")
        print(f"Example: {sys.argv[0]} test-app-nodejs-new")
        sys.exit(1)
    
    weblog_name = sys.argv[1]
    
    # Load JSON data
    print(f"{Colors.BLUE}Loading AWS SSI and VM data...{Colors.ENDC}")
    vm_data = load_json_file(VM_JSON_PATH)
    aws_ssi_data = load_json_file(AWS_SSI_JSON_PATH)
    
    # Ask for language
    language = select_language()
    
    # Get all scenarios and VMs
    all_scenarios = get_all_scenarios(aws_ssi_data)
    all_vms = get_all_virtual_machines(vm_data)
    
    # Check if this weblog already exists
    existing_scenarios, weblog_spec = get_weblog_info(aws_ssi_data, weblog_name, language)
    is_existing_weblog = bool(weblog_spec)
    
    if is_existing_weblog:
        print(f"\n{Colors.YELLOW}Weblog '{weblog_name}' ({language}) already exists in the configuration.{Colors.ENDC}")
        print(f"{Colors.YELLOW}You can now update its associated scenarios and VM compatibility.{Colors.ENDC}")
    else:
        print(f"\n{Colors.GREEN}Registering new weblog '{weblog_name}' for {language}.{Colors.ENDC}")
    
    # Select scenarios to associate with this weblog
    selected_scenarios = select_multiple_items(
        all_scenarios,
        f"Select scenarios to associate with {weblog_name} ({language}):",
        preselected=existing_scenarios
    )
    
    # Determine VM compatibility
    compatible_vms = []
    incompatible_vms = []
    
    if weblog_spec:
        # For existing weblog, get current compatibility
        for vm in all_vms:
            if is_vm_compatible_with_weblog(vm, weblog_spec):
                compatible_vms.append(vm)
            else:
                incompatible_vms.append(vm)
    
    # Display current configuration
    print_weblog_info(weblog_name, language, selected_scenarios, compatible_vms, incompatible_vms)
    
    # Ask if user wants to modify VM compatibility
    wants_to_modify_vms = False
    if is_existing_weblog:
        print(f"\n{Colors.YELLOW}Do you want to modify VM compatibility for this weblog? (y/n){Colors.ENDC}")
        wants_to_modify_vms = input().lower() == 'y'
    else:
        # New weblog always needs VM compatibility configuration
        wants_to_modify_vms = True
    
    # If modifying VM compatibility
    if wants_to_modify_vms:
        # Select VMs to be compatible with this weblog
        selected_vms = select_multiple_items(
            all_vms,
            f"Select virtual machines that should be compatible with {weblog_name} ({language}):",
            get_display_func=lambda vm: f"{vm.get('name')} ({vm.get('os_branch')})",
            preselected=compatible_vms
        )
        
        compatible_vms = selected_vms
        incompatible_vms = [vm for vm in all_vms if vm not in compatible_vms]
    
    # Confirm the changes
    print(f"\n{Colors.BOLD}Summary of changes to be made:{Colors.ENDC}")
    print(f"  - {'Update' if is_existing_weblog else 'Create'} weblog '{weblog_name}' for {language}")
    print(f"  - Associate with {len(selected_scenarios)} scenario(s)")
    print(f"  - Make compatible with {len(compatible_vms)} virtual machine(s)")
    
    print(f"\n{Colors.YELLOW}Do you want to save these changes to aws_ssi.json? (y/n){Colors.ENDC}")
    if input().lower() != 'y':
        print(f"{Colors.YELLOW}Changes were not saved.{Colors.ENDC}")
        sys.exit(0)
    
    # Update the configuration
    aws_ssi_data = update_scenario_matrix(aws_ssi_data, weblog_name, language, selected_scenarios)
    aws_ssi_data = update_weblog_spec(aws_ssi_data, weblog_name, language, compatible_vms, all_vms)
    
    # Save the changes
    save_json_file(AWS_SSI_JSON_PATH, aws_ssi_data)
    
    print(f"\n{Colors.GREEN}{Colors.BOLD}Weblog {weblog_name} ({language}) has been successfully {'updated' if is_existing_weblog else 'registered'}.{Colors.ENDC}")
    print(f"{Colors.GREEN}The changes have been saved to aws_ssi.json.{Colors.ENDC}")


if __name__ == "__main__":
    main()
