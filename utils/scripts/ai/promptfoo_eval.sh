#!/bin/bash
set -euo pipefail

# ==============================================================================
# Promptfoo Evaluation Wizard
# Interactive script to run promptfoo evaluations with provider and scenario selection
# ==============================================================================

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR

# Find repo root using git (works regardless of script location)
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"
if [[ -z "$REPO_ROOT" ]]; then
    echo "Error: Not inside a git repository" >&2
    exit 1
fi
readonly REPO_ROOT
readonly PROMPTFOO_DIR="$REPO_ROOT/.promptfoo"
readonly CONFIG_FILE="$REPO_ROOT/promptfooconfig.yaml"

# Colors
readonly C_GREEN='\033[0;32m'
readonly C_BLUE='\033[0;34m'
readonly C_YELLOW='\033[1;33m'
readonly C_CYAN='\033[0;36m'
readonly C_MAGENTA='\033[0;35m'
readonly C_RESET='\033[0m'

# ------------------------------------------------------------------------------
# Utility Functions
# ------------------------------------------------------------------------------

# Print colored message
print() {
    local color=$1
    shift
    echo -e "${color}$*${C_RESET}"
}

# Print section header
print_header() {
    print "$C_MAGENTA" "━━━ $1 ━━━"
    echo
}

# Print menu option
print_option() {
    local num=$1
    local text=$2
    local detail=${3:-}

    if [[ -n $detail ]]; then
        print "$C_GREEN" "  $num)" "$text ${C_CYAN}($detail)${C_RESET}"
    else
        print "$C_GREEN" "  $num)" "$text"
    fi
}

# Get validated numeric input
get_choice() {
    local prompt=$1
    local max=$2
    local choice

    while true; do
        read -rp "$prompt" choice

        if [[ ! $choice =~ ^[0-9]+$ ]]; then
            print "$C_YELLOW" "⚠️  Please enter a number."
            continue
        fi

        if [[ $choice -ge 0 && $choice -le $max ]]; then
            echo "$choice"
            return 0
        fi

        print "$C_YELLOW" "⚠️  Invalid choice. Please enter a number between 0 and $max."
    done
}

# ------------------------------------------------------------------------------
# Provider Functions
# ------------------------------------------------------------------------------

# Parse providers from promptfooconfig.yaml
parse_providers() {
    local providers=()
    local labels=()

    while IFS= read -r line; do
        if [[ $line =~ ^[[:space:]]*-[[:space:]]*id:[[:space:]]*[\'\"]*([^\'\"]*)[\'\"]* ]]; then
            # Found a provider - add it and a placeholder for its label
            providers+=("${BASH_REMATCH[1]}")
            labels+=("")  # Will be replaced if we find a label next
        elif [[ $line =~ ^[[:space:]]*label:[[:space:]]*[\'\"]*([^\'\"]*)[\'\"]* ]] && [[ ${#labels[@]} -gt 0 ]]; then
            # Found a label - replace the last empty label
            labels[${#labels[@]}-1]="${BASH_REMATCH[1]}"
        fi
    done < "$CONFIG_FILE"

    # Return as array format (bash 3.2 compatible)
    printf '%s\n' "${providers[@]}"
    echo '---'
    printf '%s\n' "${labels[@]}"
}

# Display and select provider
select_provider() {
    print_header "Step 1: Select Provider" >&2
    print "$C_BLUE" "Which provider would you like to use for the evaluation?" >&2
    echo >&2

    local providers_data
    providers_data=$(parse_providers)

    # Parse providers and labels (bash 3.2 compatible)
    local providers=()
    local labels=()
    local in_labels=0

    while IFS= read -r line; do
        if [[ $line == "---" ]]; then
            in_labels=1
            continue
        fi

        if [[ $in_labels -eq 0 ]]; then
            providers+=("$line")
        else
            labels+=("$line")
        fi
    done <<< "$providers_data"

    if [[ ${#providers[@]} -eq 0 ]]; then
        print "$C_YELLOW" "⚠️  No providers found in $CONFIG_FILE" >&2
        exit 1
    fi

    print_option "0" "Use ALL providers" >&2
    echo >&2

    for i in "${!providers[@]}"; do
        local num=$((i + 1))
        local label="${labels[$i]:-}"
        if [[ -n $label ]]; then
            print_option "$num" "$label" "${providers[$i]}" >&2
        else
            print_option "$num" "${providers[$i]}" >&2
        fi
    done
    echo >&2

    local choice
    choice=$(get_choice "Enter your choice (0-${#providers[@]}): " "${#providers[@]}")

    echo >&2
    if [[ $choice -eq 0 ]]; then
        print "$C_GREEN" "✓ Selected: ${C_CYAN}ALL providers" >&2
        echo "" # Return empty string for ALL
    else
        local idx=$((choice - 1))
        local selected="${providers[$idx]}"
        local selected_label="${labels[$idx]:-}"
        if [[ -n $selected_label ]]; then
            print "$C_GREEN" "✓ Selected provider: ${C_CYAN}$selected_label ($selected)" >&2
        else
            print "$C_GREEN" "✓ Selected provider: ${C_CYAN}$selected" >&2
        fi
        echo "$selected" # Return the provider ID
    fi
}

# ------------------------------------------------------------------------------
# Scenario Functions
# ------------------------------------------------------------------------------

# Find test scenario files
find_test_files() {
    find "$PROMPTFOO_DIR" -maxdepth 1 -name "tests_*.yaml" -type f | sort
}

# Extract scenario name from filename
extract_scenario_name() {
    local filename
    filename=$(basename "$1")
    filename="${filename#tests_}"
    echo "${filename%.yaml}"
}

# Display and select test scenarios
select_scenario() {
    print_header "Step 2: Select Test Scenarios" >&2

    # Find test files (bash 3.2 compatible)
    local test_files=()
while IFS= read -r file; do
        test_files+=("$file")
    done < <(find_test_files)

    if [[ ${#test_files[@]} -eq 0 ]]; then
        print "$C_YELLOW" "⚠️  No test files found in $PROMPTFOO_DIR" >&2
    exit 1
fi

    print "$C_BLUE" "Would you like to run all scenarios or select specific ones?" >&2
    echo >&2
    print_option "0" "Run ALL scenarios" >&2
    echo >&2

    for i in "${!test_files[@]}"; do
        local num=$((i + 1))
        local name
        name=$(extract_scenario_name "${test_files[$i]}")
        print_option "$num" "$name" >&2
    done
    echo >&2

    local choice
    choice=$(get_choice "Enter your choice (0-${#test_files[@]}): " "${#test_files[@]}")

    echo >&2
    if [[ $choice -eq 0 ]]; then
        print "$C_GREEN" "✓ Selected: ${C_CYAN}ALL scenarios" >&2
        echo "" # Return empty string for ALL
    else
        local idx=$((choice - 1))
        local selected="${test_files[$idx]}"
        local name
        name=$(extract_scenario_name "$selected")
        print "$C_GREEN" "✓ Selected scenario: ${C_CYAN}$name" >&2
        echo "$selected" # Return the file path
    fi
}

# ------------------------------------------------------------------------------
# Evaluation Execution
# ------------------------------------------------------------------------------

# Run promptfoo evaluation
run_evaluation() {
    local provider=${1:-}
    local config=${2:-}

    print_header "Step 3: Running Evaluation" >&2
    print "$C_BLUE" "📊 Running promptfoo evaluation..." >&2

    local cmd="promptfoo eval --no-cache"

    [[ -n $config ]] && cmd="$cmd -t $config"
    [[ -n $provider ]] && cmd="$cmd --filter-providers $provider"

    eval "$cmd"

    echo >&2
    print "$C_GREEN" "✅ Evaluation complete!" >&2
}

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

main() {
    # Print banner
    echo
    print "$C_CYAN" "╔═══════════════════════════════════════════════════════════╗"
    print "$C_CYAN" "║          ${C_YELLOW}🤖 Promptfoo Evaluation Wizard 🧙‍♂️${C_CYAN}               ║"
    print "$C_CYAN" "╚═══════════════════════════════════════════════════════════╝"
    echo

    # Step 1: Select provider
    local selected_provider
    selected_provider=$(select_provider)

    # Step 2: Select scenario
    local selected_config
    selected_config=$(select_scenario)

    # Step 3: Run evaluation
    run_evaluation "$selected_provider" "$selected_config"
}

main "$@"
