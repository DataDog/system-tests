#!/usr/bin/env python3
"""
VM Compatibility Checker for AWS SSI Weblogs

This script checks if a specific VM is compatible with the weblogs defined in aws_ssi.json.
It allows users to view and modify compatibility settings.
"""

import json
import os
import sys
from typing import Dict, List, Set, Tuple, Any

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


def update_aws_ssi_json(aws_ssi_data: dict, vm_details: dict, weblog: str, language: str, make_compatible: bool) -> dict:
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


def save_aws_ssi_json(aws_ssi_data: dict) -> None:
    """Save AWS SSI data back to the JSON file."""
    try:
        # Create a backup first
        backup_path = AWS_SSI_JSON_PATH + ".bak"
        with open(AWS_SSI_JSON_PATH, 'r') as src, open(backup_path, 'w') as backup:
            backup.write(src.read())
        
        # Write the updated data
        with open(AWS_SSI_JSON_PATH, 'w') as file:
            json.dump(aws_ssi_data, file, indent=4)
        
        print(f"{Colors.GREEN}AWS SSI configuration updated successfully.{Colors.ENDC}")
        print(f"{Colors.YELLOW}Backup saved to {backup_path}{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.RED}Error saving AWS SSI JSON: {e}{Colors.ENDC}")


def print_vm_details(vm_details: dict) -> None:
    """Print VM details in a formatted way."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}VM Details:{Colors.ENDC}")
    print(f"  Name:      {Colors.BOLD}{vm_details.get('name')}{Colors.ENDC}")
    print(f"  OS Type:   {vm_details.get('os_type')}")
    print(f"  OS Branch: {vm_details.get('os_branch')}")
    print(f"  AMI ID:    {vm_details.get('ami_id', 'N/A')}")
    if vm_details.get('disabled'):
        print(f"  {Colors.RED}Status:    Disabled{Colors.ENDC}")
    else:
        print(f"  {Colors.GREEN}Status:    Active{Colors.ENDC}")
    print()


def main():
    # Check if a VM name was provided
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <vm_name>")
        print(f"Example: {sys.argv[0]} Ubuntu_22_04_amd64")
        sys.exit(1)
    
    vm_name = sys.argv[1]
    
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
    
    # Helper function to select multiple items from a numbered list
    def select_multiple_items(items, prompt_text):
        selected_indices = []
        while True:
            print(prompt_text)
            print(f"  (Enter numbers separated by commas, 'all' to select all, or 'done' when finished)")
            for i, item in enumerate(items, 1):
                already_selected = "✓ " if i-1 in selected_indices else "  "
                print(f"  {already_selected}{i}. {item}")
            
            choice = input("Enter selection: ").strip().lower()
            
            if choice == 'done':
                break
            elif choice == 'all':
                selected_indices = list(range(len(items)))
                break
            else:
                try:
                    # Parse comma-separated numbers
                    for num in choice.split(','):
                        num = int(num.strip()) - 1
                        if 0 <= num < len(items):
                            if num not in selected_indices:
                                selected_indices.append(num)
                        else:
                            print(f"{Colors.RED}Invalid selection: {num+1}{Colors.ENDC}")
                except ValueError:
                    print(f"{Colors.RED}Please enter valid numbers separated by commas.{Colors.ENDC}")
        
        return [items[i] for i in selected_indices]

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
                            aws_ssi_data = update_aws_ssi_json(aws_ssi_data, vm_details, weblog, language_choice, True)
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
                            aws_ssi_data = update_aws_ssi_json(aws_ssi_data, vm_details, weblog, language_choice, False)
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
            save_aws_ssi_json(aws_ssi_data)
        else:
            print(f"{Colors.YELLOW}Changes were not saved.{Colors.ENDC}")
    else:
        print(f"\n{Colors.BLUE}No changes were made.{Colors.ENDC}")


if __name__ == "__main__":
    main()
