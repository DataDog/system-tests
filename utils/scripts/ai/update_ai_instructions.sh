#!/bin/bash

# Script to update AI instructions across different tools
# This script copies the content from utils/scripts/ai/ai_instructions
# to .cursorrules and .github/copilot-instructions.md

set -euo pipefail

# Define file paths
TEMPLATE_FILE="utils/scripts/ai/ai_instructions"
CURSOR_RULES_FILE=".cursorrules"
COPILOT_INSTRUCTIONS_FILE=".github/copilot-instructions.md"

# Function to display usage
usage() {
    echo "Usage: $0"
    echo "This script updates AI instructions from the template file to:"
    echo "  - .cursorrules"
    echo "  - .github/copilot-instructions.md"
    echo ""
    echo "Template source: $TEMPLATE_FILE"
}

# Function to check if template file exists
check_template_file() {
    if [[ ! -f "$TEMPLATE_FILE" ]]; then
        echo "Error: Template file '$TEMPLATE_FILE' not found!"
        echo "Please ensure you're running this script from the repository root."
        exit 1
    fi
}

# Function to create directory if it doesn't exist
ensure_directory() {
    local file_path="$1"
    local dir_path
    dir_path=$(dirname "$file_path")

    if [[ ! -d "$dir_path" ]]; then
        echo "Creating directory: $dir_path"
        mkdir -p "$dir_path"
    fi
}

# Function to backup existing file
backup_file() {
    local file_path="$1"
    local backup_path

    if [[ -f "$file_path" ]]; then
        backup_path="${file_path}.backup.$(date +%Y%m%d_%H%M%S)"
        echo "Backing up existing file: $file_path -> $backup_path"
        cp "$file_path" "$backup_path"
    fi
}

# Function to update a target file
update_file() {
    local target_file="$1"

    echo "Updating $target_file..."

    # Ensure directory exists
    ensure_directory "$target_file"

    # Backup existing file if it exists
    backup_file "$target_file"

    # Copy content from template
    cp "$TEMPLATE_FILE" "$target_file"

    echo "✅ Successfully updated $target_file"
}

# Main execution
main() {
    echo "🤖 Updating AI instructions across tools..."
    echo "Template source: $TEMPLATE_FILE"
    echo ""

    # Check if template file exists
    check_template_file

    # Update both target files
    update_file "$CURSOR_RULES_FILE"
    update_file "$COPILOT_INSTRUCTIONS_FILE"

    echo ""
    echo "🎉 All AI instruction files have been updated successfully!"
    echo ""
    echo "Updated files:"
    echo "  - $CURSOR_RULES_FILE"
    echo "  - $COPILOT_INSTRUCTIONS_FILE"
    echo ""
    echo "Backup files were created with timestamp suffix for any existing files."
    echo ""
    echo "Remember to commit these changes to keep AI instructions synchronized! 🚀"
}

# Handle help flag
if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

# Run main function
main "$@"