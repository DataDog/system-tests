#!/usr/bin/env python3
"""
AWS SSI Configuration Tool

This script combines functionality from three existing tools:
1. VM compatibility checker
2. Weblog registration
3. Scenario registration

It provides both a wizard mode and command-line parameter-based operation.
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Set, Tuple, Any, Optional


# Get the absolute path to the system-tests directory
SYSTEM_TESTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))

# Define paths to required JSON files
VM_JSON_PATH = os.path.join(SYSTEM_TESTS_DIR, "utils/virtual_machine/virtual_machines.json")
AWS_SSI_JSON_PATH = os.path.join(SYSTEM_TESTS_DIR, "utils/scripts/ci_orchestrators/aws_ssi.json")
SCENARIOS_PY_PATH = os.path.join(SYSTEM_TESTS_DIR, "utils/_context/_scenarios/__init__.py")

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


#############################
# Shared utility functions
#############################

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


def get_all_scenarios(aws_ssi_data: dict) -> List[str]:
    """Extract all unique scenario names from the AWS SSI configuration."""
    scenarios = set()
    for entry in aws_ssi_data.get("scenario_matrix", []):
        scenarios.update(entry.get("scenarios", []))
    return sorted(list(scenarios))


def get_all_virtual_machines(vm_data: dict) -> List[dict]:
    """Get all virtual machines that are not disabled."""
    return [vm for vm in vm_data.get("virtual_machines", []) if not vm.get("disabled", False)]


#############################
# VM Compatibility Checker
#############################

def get_vm_details(vm_data: dict, vm_name: str) -> dict:
    """
    Find VM details by name in the virtual_machines.json data.
    
    Args:
        vm_data: Dictionary containing virtual machines data
        vm_name: Name of the VM to find
    
    Returns:
        Dictionary with VM details or None if not found
    """
    virtual_machines = vm_data.get("virtual_machines", [])
    for vm in virtual_machines:
        if vm.get("name") == vm_name:
            return vm
    
    print(f"{Colors.RED}Error: VM with name '{vm_name}' not found.{Colors.ENDC}")
    print(f"{Colors.YELLOW}Available VMs:{Colors.ENDC}")
    for vm in virtual_machines:
        print(f"  - {vm.get('name')}")
    sys.exit(1)


def check_weblog_compatibility(
    vm_details: dict, weblog_spec: dict, weblog_name: str, language: str
) -> bool:
    """
    Check if a weblog is compatible with a VM based on the rules in aws_ssi.json.
    
    Args:
        vm_details: Dictionary with VM details
        weblog_spec: Dictionary with weblog specifications
        weblog_name: Name of the weblog to check
        language: Language of the weblog
    
    Returns:
        True if compatible, False otherwise
    """
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
            if vm_details.get("os_type") in excluded_types:
                return False
                
            # If no exclusions were triggered, the weblog is compatible
            return True
    
    # Weblog not found in specifications - assume incompatible
    return False


def get_compatible_weblogs(
    vm_details: dict, aws_ssi_data: dict
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """
    Get lists of compatible and incompatible weblogs for a VM.
    
    Args:
        vm_details: Dictionary with VM details
        aws_ssi_data: Dictionary containing AWS SSI data
    
    Returns:
        Tuple containing:
        - Dictionary with language-keyed lists of compatible weblogs
        - Dictionary with language-keyed lists of incompatible weblogs
    """
    weblog_specs = aws_ssi_data.get("weblogs_spec", {})
    scenario_matrix = aws_ssi_data.get("scenario_matrix", [])
    
    # Find all unique weblog names in scenario_matrix
    all_weblogs_by_language = {}
    for entry in scenario_matrix:
        for weblog_entry in entry.get("weblogs", []):
            for language, weblogs in weblog_entry.items():
                if language not in all_weblogs_by_language:
                    all_weblogs_by_language[language] = set()
                all_weblogs_by_language[language].update(weblogs)
    
    # Check compatibility for each weblog
    compatible_weblogs = {}
    incompatible_weblogs = {}
    
    for language, weblogs in all_weblogs_by_language.items():
        compatible_weblogs[language] = []
        incompatible_weblogs[language] = []
        
        for weblog in sorted(weblogs):
            if check_weblog_compatibility(vm_details, weblog_specs, weblog, language):
                compatible_weblogs[language].append(weblog)
            else:
                incompatible_weblogs[language].append(weblog)
    
    return compatible_weblogs, incompatible_weblogs


def update_vm_compatibility(aws_ssi_data: dict, vm_details: dict, weblog: str, language: str, make_compatible: bool) -> dict:
    """
    Update aws_ssi.json to modify compatibility settings for a weblog and VM.
    
    Args:
        aws_ssi_data: Dictionary containing AWS SSI data
        vm_details: Dictionary with VM details
        weblog: Name of the weblog to update
        language: Language of the weblog
        make_compatible: True to make compatible, False to make incompatible
    
    Returns:
        Updated AWS SSI data
    """
    weblog_specs = aws_ssi_data.get("weblogs_spec", {})
    
    # Find the weblog specification
    for weblog_entry in weblog_specs.get(language, []):
        if weblog_entry.get("name") == weblog:
            if make_compatible:
                # Remove from exact_os_branches if it restricts compatibility
                exact_branches = weblog_entry.get("exact_os_branches", [])
                if exact_branches and vm_details.get("os_branch") not in exact_branches:
                    # If there was an exact_os_branches list but our VM wasn't in it,
                    # we should not remove the restriction as it might affect other VMs.
                    # Instead, add our VM's branch to the list.
                    if "exact_os_branches" not in weblog_entry:
                        weblog_entry["exact_os_branches"] = []
                    weblog_entry["exact_os_branches"].append(vm_details.get("os_branch"))
                
                # Remove from excluded_os_branches if present
                excluded_branches = weblog_entry.get("excluded_os_branches", [])
                if vm_details.get("os_branch") in excluded_branches:
                    excluded_branches.remove(vm_details.get("os_branch"))
                    if not excluded_branches:  # If the list is now empty, remove the key
                        weblog_entry.pop("excluded_os_branches", None)
                    else:
                        weblog_entry["excluded_os_branches"] = excluded_branches
                
                # Remove from excluded_os_names if present
                excluded_names = weblog_entry.get("excluded_os_names", [])
                if vm_details.get("name") in excluded_names:
                    excluded_names.remove(vm_details.get("name"))
                    if not excluded_names:  # If the list is now empty, remove the key
                        weblog_entry.pop("excluded_os_names", None)
                    else:
                        weblog_entry["excluded_os_names"] = excluded_names
                
                # Remove from excluded_os_types if present
                excluded_types = weblog_entry.get("excluded_os_types", [])
                if vm_details.get("os_type") in excluded_types:
                    excluded_types.remove(vm_details.get("os_type"))
                    if not excluded_types:  # If the list is now empty, remove the key
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
    print(f"  CPU:       {vm_details.get('os_cpu', 'N/A')}")
    print(f"  AMI ID:    {vm_details.get('aws_config', {}).get('ami_id', 'N/A')}")
    if vm_details.get('disabled'):
        print(f"  {Colors.RED}Status:    Disabled{Colors.ENDC}")
    else:
        print(f"  {Colors.GREEN}Status:    Active{Colors.ENDC}")
    print()


def vm_compatibility_checker(vm_name: str) -> None:
    """
    Check and manage compatibility between a VM and weblogs.
    
    Args:
        vm_name: The name of the VM to check
    """
    # Load JSON data
    print(f"{Colors.BLUE}Loading VM and AWS SSI data...{Colors.ENDC}")
    vm_data = load_json_file(VM_JSON_PATH)
    aws_ssi_data = load_json_file(AWS_SSI_JSON_PATH)
    
    # Get VM details
    vm_details = get_vm_details(vm_data, vm_name)
    
    # Print VM details
    print_vm_details(vm_details)
    
    # Get compatible and incompatible weblogs
    compatible_weblogs, incompatible_weblogs = get_compatible_weblogs(vm_details, aws_ssi_data)
    
    # Display compatible weblogs
    print(f"{Colors.GREEN}{Colors.BOLD}Compatible Weblogs:{Colors.ENDC}")
    has_compatible = False
    for language, weblogs in compatible_weblogs.items():
        if weblogs:
            has_compatible = True
            print(f"  {Colors.BLUE}{language}:{Colors.ENDC}")
            for i, weblog in enumerate(weblogs, 1):
                print(f"    {i}. {weblog}")
    
    if not has_compatible:
        print(f"  {Colors.YELLOW}No compatible weblogs found.{Colors.ENDC}")
    
    # Display incompatible weblogs
    print(f"\n{Colors.RED}{Colors.BOLD}Incompatible Weblogs:{Colors.ENDC}")
    has_incompatible = False
    for language, weblogs in incompatible_weblogs.items():
        if weblogs:
            has_incompatible = True
            print(f"  {Colors.BLUE}{language}:{Colors.ENDC}")
            for i, weblog in enumerate(weblogs, 1):
                print(f"    {i}. {weblog}")
    
    if not has_incompatible:
        print(f"  {Colors.GREEN}All weblogs are compatible with this VM.{Colors.ENDC}")
    
    # Ask user if they want to modify compatibility
    changes_made = False
    
    # Ask if the user wants to make incompatible weblogs compatible
    if has_incompatible:
        print(f"\n{Colors.YELLOW}Do you want to make any incompatible weblog compatible with {vm_name}? (y/n){Colors.ENDC}")
        choice = input().lower()
        
        if choice == 'y':
            # Present languages as a numbered list
            print(f"\nSelect the language of the weblogs you want to make compatible:")
            available_languages = [lang for lang in incompatible_weblogs.keys() if incompatible_weblogs[lang]]
            for i, language in enumerate(available_languages, 1):
                print(f"  {i}. {language}")
            
            try:
                lang_index = int(input("Enter number: ")) - 1
                if 0 <= lang_index < len(available_languages):
                    language_choice = available_languages[lang_index]
                    
                    # Select multiple weblogs
                    selected_weblogs = select_multiple_items(
                        incompatible_weblogs[language_choice],
                        f"\nSelect the weblogs to make compatible with {vm_name}:"
                    )
                    
                    if selected_weblogs:
                        for weblog in selected_weblogs:
                            print(f"{Colors.YELLOW}Making {weblog} ({language_choice}) compatible with {vm_name}...{Colors.ENDC}")
                            aws_ssi_data = update_vm_compatibility(aws_ssi_data, vm_details, weblog, language_choice, True)
                            changes_made = True
                    else:
                        print(f"{Colors.BLUE}No weblogs selected for compatibility changes.{Colors.ENDC}")
                else:
                    print(f"{Colors.RED}Invalid language selection.{Colors.ENDC}")
            except ValueError:
                print(f"{Colors.RED}Please enter a valid number for language.{Colors.ENDC}")
        else:
            print(f"{Colors.BLUE}No compatibility changes made for incompatible weblogs.{Colors.ENDC}")
    
    # Ask if the user wants to make compatible weblogs incompatible
    if has_compatible:
        print(f"\n{Colors.YELLOW}Do you want to make any compatible weblog incompatible with {vm_name}? (y/n){Colors.ENDC}")
        choice = input().lower()
        
        if choice == 'y':
            # Present languages as a numbered list
            print(f"\nSelect the language of the weblogs you want to make incompatible:")
            available_languages = [lang for lang in compatible_weblogs.keys() if compatible_weblogs[lang]]
            for i, language in enumerate(available_languages, 1):
                print(f"  {i}. {language}")
            
            try:
                lang_index = int(input("Enter number: ")) - 1
                if 0 <= lang_index < len(available_languages):
                    language_choice = available_languages[lang_index]
                    
                    # Select multiple weblogs
                    selected_weblogs = select_multiple_items(
                        compatible_weblogs[language_choice],
                        f"\nSelect the weblogs to make incompatible with {vm_name}:"
                    )
                    
                    if selected_weblogs:
                        for weblog in selected_weblogs:
                            print(f"{Colors.YELLOW}Making {weblog} ({language_choice}) incompatible with {vm_name}...{Colors.ENDC}")
                            aws_ssi_data = update_vm_compatibility(aws_ssi_data, vm_details, weblog, language_choice, False)
                            changes_made = True
                    else:
                        print(f"{Colors.BLUE}No weblogs selected for compatibility changes.{Colors.ENDC}")
                else:
                    print(f"{Colors.RED}Invalid language selection.{Colors.ENDC}")
            except ValueError:
                print(f"{Colors.RED}Please enter a valid number for language.{Colors.ENDC}")
        else:
            print(f"{Colors.BLUE}No compatibility changes made for compatible weblogs.{Colors.ENDC}")
    
    # Save changes if any were made
    if changes_made:
        print(f"\n{Colors.YELLOW}Do you want to save the changes to aws_ssi.json? (y/n){Colors.ENDC}")
        if input().lower() == 'y':
            save_json_file(AWS_SSI_JSON_PATH, aws_ssi_data)
        else:
            print(f"{Colors.YELLOW}Changes were not saved.{Colors.ENDC}")
    else:
        print(f"\n{Colors.BLUE}No changes were made.{Colors.ENDC}")


#############################
# Weblog Registration
#############################

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


def register_weblog(weblog_name: str, language: str = None) -> None:
    """
    Register or update a weblog in the AWS SSI configuration.
    
    Args:
        weblog_name: The name of the weblog to register
        language: Optional language of the weblog, will prompt if not provided
    """
    # Load JSON data
    print(f"{Colors.BLUE}Loading AWS SSI and VM data...{Colors.ENDC}")
    vm_data = load_json_file(VM_JSON_PATH)
    aws_ssi_data = load_json_file(AWS_SSI_JSON_PATH)
    
    # Ask for language if not provided
    if language is None:
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
        return
    
    # Update the configuration
    aws_ssi_data = update_scenario_matrix(aws_ssi_data, weblog_name, language, selected_scenarios)
    aws_ssi_data = update_weblog_spec(aws_ssi_data, weblog_name, language, compatible_vms, all_vms)
    
    # Save the changes
    save_json_file(AWS_SSI_JSON_PATH, aws_ssi_data)
    
    print(f"\n{Colors.GREEN}{Colors.BOLD}Weblog {weblog_name} ({language}) has been successfully {'updated' if is_existing_weblog else 'registered'}.{Colors.ENDC}")
    print(f"{Colors.GREEN}The changes have been saved to aws_ssi.json.{Colors.ENDC}")


#############################
# Scenario Registration
#############################

def get_all_weblogs_by_language(aws_ssi_data: dict) -> Dict[str, List[str]]:
    """
    Extract all weblogs grouped by language from the AWS SSI configuration.
    
    Args:
        aws_ssi_data: The AWS SSI configuration data
        
    Returns:
        Dictionary with language as key and list of weblog names as value
    """
    all_weblogs = {}
    
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
    return {lang: sorted(list(weblogs)) for lang, weblogs in all_weblogs.items()}


def get_scenario_weblogs(aws_ssi_data: dict, scenario_name: str) -> Dict[str, List[str]]:
    """
    Get all weblogs associated with a specific scenario.
    
    Args:
        aws_ssi_data: The AWS SSI configuration data
        scenario_name: Name of the scenario to check
        
    Returns:
        Dictionary with language as key and list of weblog names as value
    """
    scenario_weblogs = {}
    
    for entry in aws_ssi_data.get("scenario_matrix", []):
        if scenario_name in entry.get("scenarios", []):
            for weblog_entry in entry.get("weblogs", []):
                for language, weblogs in weblog_entry.items():
                    if language not in scenario_weblogs:
                        scenario_weblogs[language] = []
                    scenario_weblogs[language].extend(weblogs)
    
    return scenario_weblogs


def update_scenario_in_matrix(aws_ssi_data: dict, scenario_name: str, 
                             selected_weblogs_by_language: Dict[str, List[str]]) -> dict:
    """
    Update the scenario_matrix section of the AWS SSI configuration.
    
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
    
    # Create a new weblog entry for the selected weblogs
    weblog_entry = {}
    for language, weblogs in selected_weblogs_by_language.items():
        if weblogs:  # Only add non-empty weblog lists
            weblog_entry[language] = weblogs
    
    # Create the new scenario entry
    new_entry = {
        "scenarios": [scenario_name],
        "weblogs": [weblog_entry] if weblog_entry else []
    }
    
    # Replace existing entry or add a new one
    if entry_index >= 0:
        scenario_matrix[entry_index] = new_entry
    else:
        scenario_matrix.append(new_entry)
    
    aws_ssi_data["scenario_matrix"] = scenario_matrix
    return aws_ssi_data


def print_scenario_info(scenario_name: str, 
                       selected_weblogs_by_language: Dict[str, List[str]]) -> None:
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
    """
    Check if the scenario is defined in the _Scenarios class in __init__.py.
    This is a simple check that just warns the user but doesn't prevent registration.
    
    Args:
        scenario_name: Name of the scenario to check
    
    Returns:
        True if found, False otherwise
    """
    if not os.path.exists(SCENARIOS_PY_PATH):
        print(f"{Colors.YELLOW}Warning: Could not find scenarios definition file. Skipping check.{Colors.ENDC}")
        return False
    
    try:
        with open(SCENARIOS_PY_PATH, 'r') as f:
            content = f.read()
            # Look for the scenario name in the file
            if f'"{scenario_name}"' in content or f"'{scenario_name}'" in content:
                return True
            return False
    except Exception as e:
        print(f"{Colors.YELLOW}Warning: Error checking scenario definition: {str(e)}{Colors.ENDC}")
        return False


def register_scenario(scenario_name: str) -> None:
    """
    Register or update a scenario in the AWS SSI configuration.
    
    Args:
        scenario_name: The name of the scenario to register
    """
    scenario_name = scenario_name.upper()  # Convert to uppercase as per convention
    
    # Load JSON data
    print(f"{Colors.BLUE}Loading AWS SSI configuration...{Colors.ENDC}")
    aws_ssi_data = load_json_file(AWS_SSI_JSON_PATH)
    
    # Check if the scenario exists in the _Scenarios class
    scenario_defined = check_scenario_in_class(scenario_name)
    if not scenario_defined:
        print(f"{Colors.YELLOW}Warning: The scenario '{scenario_name}' does not appear to be defined in the _Scenarios class.{Colors.ENDC}")
        print(f"{Colors.YELLOW}You should define it in utils/_context/_scenarios/__init__.py before using it.{Colors.ENDC}")
        
        print(f"\n{Colors.YELLOW}Do you want to continue anyway? (y/n){Colors.ENDC}")
        if input().lower() != 'y':
            print(f"{Colors.BLUE}Script execution cancelled.{Colors.ENDC}")
            return
    
    # Get all weblogs by language
    all_weblogs_by_language = get_all_weblogs_by_language(aws_ssi_data)
    
    # Get weblogs currently associated with the scenario
    current_weblogs_by_language = get_scenario_weblogs(aws_ssi_data, scenario_name)
    
    # Check if the scenario already exists
    is_existing_scenario = any(scenario_name in entry.get("scenarios", []) 
                            for entry in aws_ssi_data.get("scenario_matrix", []))
    
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
            weblogs,
            f"Select {language} weblogs for scenario '{scenario_name}':",
            preselected=preselected
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
    if input().lower() != 'y':
        print(f"{Colors.YELLOW}Changes were not saved.{Colors.ENDC}")
        return
    
    # Update the configuration
    aws_ssi_data = update_scenario_in_matrix(aws_ssi_data, scenario_name, selected_weblogs_by_language)
    
    # Save the changes
    save_json_file(AWS_SSI_JSON_PATH, aws_ssi_data)
    
    print(f"\n{Colors.GREEN}{Colors.BOLD}Scenario {scenario_name} has been successfully {'updated' if is_existing_scenario else 'registered'}.{Colors.ENDC}")
    print(f"{Colors.GREEN}The changes have been saved to aws_ssi.json.{Colors.ENDC}")
    
    # Provide next steps
    if not scenario_defined:
        print(f"\n{Colors.YELLOW}Remember to define this scenario in utils/_context/_scenarios/__init__.py{Colors.ENDC}")
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


#############################
# Main wizard functionality
#############################

def show_wizard_menu() -> int:
    """
    Show the main wizard menu and return the user's choice.
    
    Returns:
        Integer representing the user's choice
    """
    print(f"\n{Colors.HEADER}{Colors.BOLD}AWS SSI Configuration Tool{Colors.ENDC}")
    print(f"\nWhat would you like to do?")
    print(f"  1. Check VM compatibility with weblogs")
    print(f"  2. Register or update a weblog")
    print(f"  3. Register or update a scenario")
    print(f"  4. Exit")
    
    while True:
        try:
            choice = int(input("\nEnter your choice (1-4): "))
            if 1 <= choice <= 4:
                return choice
            print(f"{Colors.RED}Please enter a number between 1 and 4.{Colors.ENDC}")
        except ValueError:
            print(f"{Colors.RED}Please enter a valid number.{Colors.ENDC}")


def run_wizard() -> None:
    """Run the interactive wizard."""
    while True:
        choice = show_wizard_menu()
        
        if choice == 1:  # VM compatibility checker
            print(f"\n{Colors.BOLD}VM Compatibility Checker{Colors.ENDC}")
            vm_name = input("Enter the name of the VM: ")
            vm_compatibility_checker(vm_name)
        
        elif choice == 2:  # Weblog registration
            print(f"\n{Colors.BOLD}Weblog Registration{Colors.ENDC}")
            weblog_name = input("Enter the name of the weblog: ")
            register_weblog(weblog_name)
        
        elif choice == 3:  # Scenario registration
            print(f"\n{Colors.BOLD}Scenario Registration{Colors.ENDC}")
            scenario_name = input("Enter the name of the scenario: ")
            register_scenario(scenario_name)
        
        elif choice == 4:  # Exit
            print(f"\n{Colors.GREEN}Thank you for using the AWS SSI Configuration Tool. Goodbye!{Colors.ENDC}")
            break
        
        # After completing a task, ask if the user wants to continue
        if choice != 4:
            print(f"\n{Colors.YELLOW}Do you want to perform another task? (y/n){Colors.ENDC}")
            if input().lower() != 'y':
                print(f"\n{Colors.GREEN}Thank you for using the AWS SSI Configuration Tool. Goodbye!{Colors.ENDC}")
                break


#############################
# Command-line interface
#############################

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="AWS SSI Configuration Tool"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # VM compatibility checker
    vm_parser = subparsers.add_parser(
        "vm", help="Check VM compatibility with weblogs"
    )
    vm_parser.add_argument("vm_name", help="Name of the VM to check")
    
    # Weblog registration
    weblog_parser = subparsers.add_parser(
        "weblog", help="Register or update a weblog"
    )
    weblog_parser.add_argument("weblog_name", help="Name of the weblog to register")
    weblog_parser.add_argument(
        "--language", "-l", help="Language of the weblog (nodejs, java, python, dotnet, ruby, php)"
    )
    
    # Scenario registration
    scenario_parser = subparsers.add_parser(
        "scenario", help="Register or update a scenario"
    )
    scenario_parser.add_argument("scenario_name", help="Name of the scenario to register")
    
    return parser.parse_args()


def main():
    """Main function."""
    # Check if arguments were provided
    if len(sys.argv) > 1:
        args = parse_args()
        
        if args.command == "vm":
            vm_compatibility_checker(args.vm_name)
        elif args.command == "weblog":
            register_weblog(args.weblog_name, args.language)
        elif args.command == "scenario":
            register_scenario(args.scenario_name)
    else:
        # If no arguments, run in wizard mode
        run_wizard()


if __name__ == "__main__":
    main()
