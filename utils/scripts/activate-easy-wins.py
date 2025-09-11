from pathlib import Path
import sys
path_root = Path(__file__).parents[2]
sys.path.append(str(path_root))

import os
import yaml
import manifests.parser.core as manifest_parser
import json
import urllib.request
import argparse
from collections import defaultdict
import re

FPD_URL = "https://dd-feature-parity.azurewebsites.net/Tests/Groups"


def fetch_fpd_data():
    """Fetch test data from the Feature Parity Dashboard API"""
    req = urllib.request.Request(FPD_URL, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        data = json.load(resp)
        return data


def extract_test_class_from_path(test_path):
    """Extract test class name from test path like 'tests/foo.py::TestClass::test_method'"""
    if "::" not in test_path:
        return None
    
    # Split by :: and take up to the test class (not individual test method)
    parts = test_path.split("::")
    if len(parts) >= 2:
        # Return path up to and including the test class
        return f"{parts[0]}::{parts[1]}"
    return None


def analyze_test_classes(fpd_data):
    """Analyze FPD data to find test classes where all tests have passed or xpassed status per language"""
    # Group tests by test class and language, track all outcomes
    test_class_language_outcomes = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    
    for test_group in fpd_data:
        language = test_group.get('language', '')
        scenario = test_group.get('scenario', '')
        environment = test_group.get('environment', '')
        variant = test_group.get('variant', '*')  # Default variant is '*'
        
        # Create a key for this specific environment (language is handled separately now)
        env_key = f"{scenario}_{environment}" if environment else scenario
        
        for test_run in test_group.get('systemTestRuns', []):
            test_path = test_run.get('testPath', '')
            original_outcome = test_run.get('originalOutcome', '')
            
            test_class = extract_test_class_from_path(test_path)
            if test_class:
                # Store outcomes grouped by test_class -> language -> env_key
                test_class_language_outcomes[test_class][language][env_key].append((variant, original_outcome))
    
    # Find test classes where ALL outcomes for a specific language are passed or xpassed
    easy_wins = {}
    
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
            if all_outcomes_for_language and all(outcome in ['xpassed', 'passed'] for outcome in all_outcomes_for_language):
                if test_class not in easy_wins:
                    easy_wins[test_class] = []
                # Add entries with language information included
                for env_key in env_keys_for_language:
                    easy_wins[test_class].append((language, env_key, '*'))  # Include language, env, variant
    
    return easy_wins


def get_language_from_env_key(env_key):
    """Extract language from environment key"""
    # Environment keys are like '2_parametric_', '5_integrations_'
    # Map numeric language IDs to actual language names
    language_map = {
        '2': 'dotnet',
        '3': 'nodejs', 
        '4': 'php',
        '5': 'python',
        '6': 'golang',   
        '7': 'ruby',
        '8': 'java',
        '9': 'cpp'
    }
    
    language_id = env_key.split('_')[0]
    return language_map.get(language_id, f'unknown_{language_id}')


def test_exists_in_manifest(test_class, manifest_data):
    """Check if a test class path exists in the manifest data structure"""
    path_parts = test_class.split('/')
    current = manifest_data
    
    # Navigate through the nested structure
    for part in path_parts[:-1]:
        if part not in current:
            return False
        current = current[part]
    
    # Handle the final file::class part
    final_part = path_parts[-1]
    if '::' in final_part:
        file_name, class_name = final_part.split('::', 1)
        return file_name in current and class_name in current[file_name]
    else:
        return final_part in current


def test_is_missing_feature_or_bug(test_class, manifest_file):
    """Check if a test class is currently marked as missing_feature, bug, or incomplete_test_app in the manifest file"""
    if '::' not in test_class:
        return False
    
    path_parts = test_class.split('/')
    file_name, class_name = path_parts[-1].split('::', 1)
    
    try:
        with open(manifest_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Look for the test class in the manifest
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f"{class_name}:"):
                # Extract the status after the colon
                if ": " in stripped:
                    status_part = stripped.split(": ", 1)[1]
                    
                    # Handle YAML multiline indicators like >- or |-
                    if status_part in ['>-', '|-', '>', '|']:
                        # Read the next line to get the actual value
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            return next_line.startswith('missing_feature') or next_line.startswith('bug') or next_line.startswith('incomplete_test_app')
                    
                    # Direct check for missing_feature, bug, or incomplete_test_app
                    return status_part.startswith('missing_feature') or status_part.startswith('bug') or status_part.startswith('incomplete_test_app')
        
        return False
    except:
        return False


def is_already_activated(test_class, manifest_file):
    """Check if a test class doesn't have a special status (bug, missing_feature, etc.) - meaning it's already activated"""
    if '::' not in test_class:
        return False
    
    path_parts = test_class.split('/')
    file_name, class_name = path_parts[-1].split('::', 1)
    
    # Special statuses that indicate the test is NOT already activated
    special_statuses = ['bug', 'missing_feature', 'incomplete_test_app', 'irrelevant']
    
    try:
        with open(manifest_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Look for the test class in the manifest
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f"{class_name}:"):
                # Extract the status after the colon
                if ": " in stripped:
                    status_part = stripped.split(": ", 1)[1]
                    
                    # Handle YAML multiline indicators like >- or |-
                    if status_part in ['>-', '|-', '>', '|']:
                        # Read the next line to get the actual value
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            first_word = next_line.split()[0] if next_line.split() else ""
                            # Check if it starts with any special status
                            return not any(first_word.startswith(status) for status in special_statuses)
                    
                    # Remove any comments
                    clean_status = status_part.split(" #")[0].split(" (")[0].strip()
                    # Check if it starts with any special status
                    return not any(clean_status.startswith(status) for status in special_statuses)
        
        return False  # Not found in manifest
    except:
        return False


def get_test_status_reason(test_class, manifest_file):
    """Get the reason why a test class is not being updated"""
    if '::' not in test_class:
        return "not_a_test_class"
    
    path_parts = test_class.split('/')
    file_name, class_name = path_parts[-1].split('::', 1)
    
    try:
        with open(manifest_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Look for the test class in the manifest
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f"{class_name}:"):
                # Extract the status after the colon
                if ": " in stripped:
                    status_part = stripped.split(": ", 1)[1]
                    
                    # Handle YAML multiline indicators like >- or |-
                    if status_part in ['>-', '|-', '>', '|']:
                        # Read the next line(s) to get the actual value
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            # Extract the first word as the status
                            first_word = next_line.split()[0] if next_line.split() else status_part
                            return f"current_status: {first_word} (multiline YAML)"
                        else:
                            return f"current_status: {status_part} (incomplete multiline)"
                    
                    # Remove any comments
                    if " #" in status_part:
                        status_part = status_part.split(" #")[0].strip()
                    if " (" in status_part:
                        status_part = status_part.split(" (")[0].strip()
                    return f"current_status: {status_part}"
                else:
                    return "has_variant_structure"
        
        return "not_in_manifest"
    except Exception as e:
        return f"error_reading_manifest: {e}"


def get_all_variants_for_language(language):
    """Get all possible variants for a language by scanning Dockerfiles"""
    import os
    import glob
    
    docker_dir = f"utils/build/docker/{language}"
    if not os.path.exists(docker_dir):
        return []
    
    variants = set()
    
    # Look for .Dockerfile files (these are the actual variants)
    dockerfile_pattern = os.path.join(docker_dir, "*.Dockerfile")
    for dockerfile in glob.glob(dockerfile_pattern):
        filename = os.path.basename(dockerfile)
        if filename.endswith('.Dockerfile'):
            variant = filename[:-len('.Dockerfile')]
            # Skip base dockerfiles - they're not variants, just foundations
            if not '.base' in variant:
                variants.add(variant)
    
    # Add parametric variant if parametric directory exists
    if os.path.exists(os.path.join(docker_dir, 'parametric')):
        variants.add(f'parametric-{language}')
    
    return sorted(list(variants))


def should_use_concise_format(variants, language):
    """Determine if we should use concise 'test: xpass' format instead of variant structure"""
    # By default, use concise format when all variants pass (indicated by '*')
    # The analyze_test_classes function now uses '*' to indicate all tested variants passed
    return '*' in variants


def update_manifest_file_with_variants(test_class, language, variants, version="xpass"):
    """Update manifest file with variant-specific test activation"""
    manifest_file = f"manifests/{language}.yml"
    
    if not os.path.exists(manifest_file):
        print(f"Warning: Manifest file {manifest_file} does not exist")
        return False
    
    try:
        # Read the original content
        with open(manifest_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Parse test path
        path_parts = test_class.split('/')
        if '::' not in path_parts[-1]:
            print(f"Skipping {test_class}: Not a test class (no :: found)")
            return False
            
        file_name, class_name = path_parts[-1].split('::', 1)
        
        # Look for the exact test class line in the file  
        # We need to find missing_feature or bug entries, prioritizing them over existing configurations
        target_indices = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Check for missing_feature, bug, or incomplete_test_app patterns
            missing_feature_match = stripped == f"{class_name}: missing_feature" or stripped.startswith(f"{class_name}: missing_feature")
            bug_match = stripped == f"{class_name}: bug" or stripped.startswith(f"{class_name}: bug")
            incomplete_test_app_match = stripped == f"{class_name}: incomplete_test_app" or stripped.startswith(f"{class_name}: incomplete_test_app")
            
            # Check for multiline YAML patterns (e.g., "ClassName: >-" followed by "missing_feature")
            multiline_match = False
            multiline_missing_feature = False
            multiline_bug = False
            multiline_incomplete_test_app = False
            
            if stripped.startswith(f"{class_name}: >-") or stripped.startswith(f"{class_name}: |-") or stripped.startswith(f"{class_name}: >") or stripped.startswith(f"{class_name}: |"):
                # Check the next line for the actual status
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    multiline_missing_feature = next_line.startswith('missing_feature')
                    multiline_bug = next_line.startswith('bug')
                    multiline_incomplete_test_app = next_line.startswith('incomplete_test_app')
                    multiline_match = multiline_missing_feature or multiline_bug or multiline_incomplete_test_app
            
            if missing_feature_match or bug_match or incomplete_test_app_match or multiline_match:
                # For multiline, use the multiline flags; for direct, use the direct flags
                target_missing_feature = missing_feature_match or multiline_missing_feature
                target_bug = bug_match or multiline_bug  
                target_incomplete_test_app = incomplete_test_app_match or multiline_incomplete_test_app
                target_indices.append((i, target_missing_feature, target_bug, target_incomplete_test_app))
                
        if target_indices:
            # Use the first missing_feature, bug, or incomplete_test_app match
            i, missing_feature_match, bug_match, incomplete_test_app_match = target_indices[0]
            line = lines[i]
            
            # Determine if we should use concise format
            use_concise = should_use_concise_format(variants, language)
            
            if use_concise:
                # Handle multiline YAML vs direct format
                base_indent = len(line) - len(line.lstrip())
                new_line = ' ' * base_indent + f"{class_name}: {version}\n"
                
                # Check if this is a multiline YAML case that needs multiple lines removed
                lines_to_replace = 1
                if line.strip().endswith('>-') or line.strip().endswith('|-') or line.strip().endswith('>') or line.strip().endswith('|'):
                    # This is multiline YAML, need to remove continuation lines too
                    # Look for lines that are indented more than the current line
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j]
                        # Check if this line is a continuation (more indented than base_indent)
                        if next_line.strip() == '':
                            # Skip empty lines
                            j += 1
                            continue
                        elif len(next_line) - len(next_line.lstrip()) > base_indent:
                            # This line is more indented than the base, so it's a continuation
                            lines_to_replace += 1
                            j += 1
                        else:
                            # This line is not more indented, so we've reached the end of the multiline content
                            break
                
                # Replace the line(s)
                lines[i:i+lines_to_replace] = [new_line]
                
                # Write back the file
                with open(manifest_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                
                original_status = "missing_feature" if missing_feature_match else ("bug" if bug_match else "incomplete_test_app")
                print(f"Updated {manifest_file}: {test_class} = {version} (was {original_status})")
                return True
            else:
                # Found a missing_feature or bug entry - replace with variant structure
                base_indent = len(line) - len(line.lstrip())
                variant_indent = base_indent + 2
                
                # Create the new variant structure
                new_lines = []
                new_lines.append(' ' * base_indent + f"{class_name}:\n")
                
                # Add '*': missing_feature for other variants not in our list
                original_status = "missing_feature" if missing_feature_match else ("bug" if bug_match else "incomplete_test_app")
                comment = " (was bug)" if bug_match else (" (was incomplete_test_app)" if incomplete_test_app_match else "")
                new_lines.append(' ' * variant_indent + f"'*': {original_status}{comment}\n")
                
                # Add specific variants that pass
                for variant in sorted(variants):
                    if variant == '*':
                        continue  # Skip the wildcard, we handle it above
                    variant_key = f"'{variant}'" if variant != '*' else "'*'"
                    new_lines.append(' ' * variant_indent + f"{variant_key}: {version}\n")
                
                # Check if this is a multiline YAML case that needs multiple lines removed
                lines_to_replace = 1
                if line.strip().endswith('>-') or line.strip().endswith('|-') or line.strip().endswith('>') or line.strip().endswith('|'):
                    # This is multiline YAML, need to remove continuation lines too
                    # Look for lines that are indented more than the current line
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j]
                        # Check if this line is a continuation (more indented than base_indent)
                        if next_line.strip() == '':
                            # Skip empty lines
                            j += 1
                            continue
                        elif len(next_line) - len(next_line.lstrip()) > base_indent:
                            # This line is more indented than the base, so it's a continuation
                            lines_to_replace += 1
                            j += 1
                        else:
                            # This line is not more indented, so we've reached the end of the multiline content
                            break
                
                # Replace the line(s) with the new structure
                lines[i:i+lines_to_replace] = new_lines
                
                # Write back the file
                with open(manifest_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                
                variants_str = ', '.join(sorted(variants))
                print(f"Updated {manifest_file}: {test_class} = {version} for variants: {variants_str} (was {original_status})")
                return True
        
        # Check if test class exists with other configurations
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == f"{class_name}:" or stripped.startswith(f"{class_name}:"):
                print(f"Skipping {manifest_file}: {test_class} already has a configuration (no missing_feature/bug/incomplete_test_app found)")
                return False
        
        # Test class not found in manifest
        print(f"Skipping {manifest_file}: {test_class} not found in manifest")
        return False
        
    except Exception as e:
        print(f"Error updating {manifest_file}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Activate test classes with all xpass tests")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Show what would be updated without making changes")
    parser.add_argument("--language", type=str, 
                       help="Only process specific language (e.g., python, java)")
    parser.add_argument("--version", type=str, default="xpass",
                       help="Version value to set for activated test classes (default: xpass)")
    parser.add_argument("--language-versions", type=str,
                       help="Specify different versions per language in format: cpp=v1.2.3,python=v2.0.0,java=xpass (languages not specified use --version default)")
    parser.add_argument("--conservative", action="store_true", default=False,
                       help="Only update tests that are marked as missing_feature, bug, or incomplete_test_app in manifest files")
    parser.add_argument("--force-add", action="store_true", 
                       help="Add missing tests even if they don't exist in manifests")
    args = parser.parse_args()
    
    # Conservative mode is the default unless --force-add is specified
    if not args.force_add:
        args.conservative = True
    
    # Parse language-specific versions
    language_versions = {}
    if args.language_versions:
        try:
            for pair in args.language_versions.split(','):
                if '=' in pair:
                    lang, version = pair.strip().split('=', 1)
                    language_versions[lang.strip()] = version.strip()
                else:
                    print(f"Warning: Invalid format in language-versions: '{pair}'. Expected format: language=version")
        except Exception as e:
            print(f"Error parsing language-versions: {e}")
            return
    
    # Function to get version for a specific language
    def get_version_for_language(language):
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
    by_language = defaultdict(list)
    for test_class, lang_env_variant_tuples in easy_wins.items():
        for language, env_key, variant in lang_env_variant_tuples:
            language_name = get_language_from_env_key(f"{language}_")  # Convert numeric to name
            if args.language is None or language_name == args.language:
                by_language[language_name].append((test_class, variant))
    
    # Track tests that are not being updated and the reasons why
    not_updated_tests = defaultdict(list)
    # Track tests that are already activated (have version numbers)
    already_activated_tests = defaultdict(list)
    
    # Categorize all easy wins first (before conservative filtering)
    for language, test_class_variants in by_language.items():
        manifest_file = f"manifests/{language}.yml"
        if os.path.exists(manifest_file):
            for test_class, variant in test_class_variants:
                if is_already_activated(test_class, manifest_file):
                    # Test is already activated with a version number
                    status_reason = get_test_status_reason(test_class, manifest_file)
                    already_activated_tests[language].append((test_class, status_reason))
                elif not test_is_missing_feature_or_bug(test_class, manifest_file):
                    reason = get_test_status_reason(test_class, manifest_file)
                    not_updated_tests[language].append((test_class, reason))
    
    # If conservative mode, filter to only tests that exist in manifests
    if args.conservative:
        filtered_by_language = {}
        for language, test_class_variants in by_language.items():
            manifest_file = f"manifests/{language}.yml"
            if os.path.exists(manifest_file):
                filtered_classes = []
                for test_class, variant in test_class_variants:
                    # Check if this test class exists as missing_feature or bug
                    if test_is_missing_feature_or_bug(test_class, manifest_file):
                        filtered_classes.append((test_class, variant))
                
                if filtered_classes:
                    filtered_by_language[language] = filtered_classes
        
        by_language = filtered_by_language
        print(f"\nConservative mode: Only updating tests marked as missing_feature, bug, or incomplete_test_app")
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
                for test_class in sorted(set(test_classes))[:3]:  # Show first 3 per reason
                    print(f"      - {test_class}")
                if len(set(test_classes)) > 3:
                    print(f"      ... and {len(set(test_classes)) - 3} more")
    elif not already_activated_tests:
        print(f"\nAll passed/xpassed tests are being updated.")
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
            manifest_file = f"manifests/{language}.yml"
            tests_to_update = []
            if os.path.exists(manifest_file):
                for test_class, variant in test_class_variants:
                    if not is_already_activated(test_class, manifest_file):
                        tests_to_update.append((test_class, variant))
            else:
                tests_to_update = test_class_variants
            
            if tests_to_update:
                print(f"\n{language}.yml:")
                # Group by test class to show variants together
                by_test_class = defaultdict(list)
                for test_class, variant in tests_to_update:
                    by_test_class[test_class].append(variant)
                
                for test_class in sorted(by_test_class.keys()):
                    variants = sorted(set(by_test_class[test_class]))
                    if len(variants) == 1 and variants[0] == '*':
                        print(f"  {test_class}")
                    else:
                        print(f"  {test_class} (variants: {', '.join(variants)})")
    else:
        print("\nUpdating manifest files...")
        total_updated = 0
        for language, test_class_variants in sorted(by_language.items()):
            # Group by test class to avoid duplicates
            by_test_class = defaultdict(set)
            for test_class, variant in test_class_variants:
                by_test_class[test_class].add(variant)
            
            for test_class in sorted(by_test_class.keys()):
                variants = sorted(by_test_class[test_class])
                # Update with variant-specific entries
                version_for_language = get_version_for_language(language)
                if update_manifest_file_with_variants(test_class, language, variants, version_for_language):
                    total_updated += 1
        
        print(f"\nCompleted! Updated {total_updated} test class entries across manifest files.")


if __name__ == "__main__":
    main()
