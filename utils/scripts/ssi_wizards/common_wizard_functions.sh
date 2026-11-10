#!/bin/bash
# shellcheck disable=all
#This script was generated using chatgpt

# shellcheck source=wizard_usage.sh
source "$(dirname "${BASH_SOURCE[0]}")/wizard_usage.sh"

# 🎨 Colors for styling
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
CYAN='\033[1;36m'
NC='\033[0m' # No Color

# Function: Add blank lines for better UX
spacer() {
    echo ""
    echo "-----------------------------------------------"
    echo ""
}
welcome() {
    echo "========================================================="
    echo "🚀 Welcome to System-Tests $1 Wizard 🚀"
    echo "========================================================="
    echo ""
}

# Function to check AWS account access
check_aws_account_access() {
    wizard_usage_step aws_account
    local account_name="$1"
    local aws_profile="sso-${account_name}-account-admin"

    if ! aws-vault exec "$aws_profile" -- aws s3 ls &>/dev/null; then
        echo "❌ AWS environment check failed for account: ${account_name}"
        echo ""
        echo "📚 Please follow these guides to set up AWS access:"
        echo "   1. AWS SSO Getting Started:"
        echo "      👉 https://datadoghq.atlassian.net/wiki/spaces/ENG/pages/2498068557/AWS+SSO+Getting+Started"
        echo ""
        echo "   2. Request AWS account access (if you don't have it):"
        echo "      👉 https://datadoghq.atlassian.net/jira/software/c/projects/CLOUDA/forms/form/direct/4/26949"
        echo ""
        echo "⚠️ Exiting wizard to prevent further issues."
        exit 1
    fi
}

load_requirements() {
    wizard_usage_step requirements
    echo "🚀 Loading system-tests requirements..."
    ./build.sh -i runner
    if [[ $? -ne 0 ]]; then
        echo "❌ Error: Failed to load system-tests requirements. Please check the logs."
        exit 1
    fi
    echo "✅ System-tests requirements loaded successfully."
    echo "🔄 Activating virtual environment..."
    # shellcheck source=/dev/null
    source venv/bin/activate
    echo "✅ Virtual environment activated."
}

ask_load_requirements() {
    wizard_usage_step requirements
    spacer
    echo -e "${YELLOW}📌 Step: system-tests requirements${NC}"
    echo "🔧 Do you want to load the system-tests requirements?"
    echo "This will execute: ./build.sh -i runner"
    read -p "Run this setup? (y/n): " load_choice
    if [[ "$load_choice" =~ ^[Yy]$ ]]; then
        load_requirements
    else
        echo "⚠️ Skipping system-tests requirements setup."
    fi
}

ask_for_test_language() {
    wizard_usage_step language
    spacer
    echo -e "${YELLOW}📌 Step: Choose the language to test${NC}"
    if [[ -n "$TEST_LIBRARY" ]]; then
        echo "✅ TEST_LIBRARY is already set to: ${TEST_LIBRARY}"
    else
        echo "🧪 Select the language you want to test:"
        echo "1) Java"
        echo "2) Node.js"
        echo "3) Python"
        echo "4) .NET"
        echo "5) Ruby (not supported by docker-ssi)"
        echo "6) PHP"

        while true; do
            read -p "Enter the number of your choice (1-6): " choice
            case $choice in
                1) TEST_LIBRARY="java"; break;;
                2) TEST_LIBRARY="nodejs"; break;;
                3) TEST_LIBRARY="python"; break;;
                4) TEST_LIBRARY="dotnet"; break;;
                5) TEST_LIBRARY="ruby"; break;;
                6) TEST_LIBRARY="php"; break;;
                *) echo "❌ Invalid choice. Please select a number between 1 and 6.";;
            esac
        done

        export TEST_LIBRARY
        echo "✅ Selected test language: $TEST_LIBRARY"
    fi
    WIZARD_LIBRARY="${TEST_LIBRARY}"
    export WIZARD_LIBRARY
}
# 🎨 Colors for styling
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
CYAN='\033[1;36m'
NC='\033[0m' # No Color

load_workflow_data(){
    wizard_usage_step workflow
    spacer
    echo "🔄 Running Python script to compute workflow parameters..."

    # Run the Python script and capture the JSON output
    WORKFLOW_JSON=$(python utils/scripts/compute-workflow-parameters.py "$TEST_LIBRARY" -g "$1" --parametric-job-count 1 --ci-environment "prod" --format json)
    export WORKFLOW_JSON=$(echo "$WORKFLOW_JSON" | jq ".$2")

    echo "TEST LIBRARY: $TEST_LIBRARY"
    echo "group: $1"
    if [[ $? -ne 0 ]]; then
        echo "❌ Error: Failed to execute the Python script."
        exit 1
    fi

    echo "✅ Successfully retrieved workflow parameters."
}

select_scenario() {
    wizard_usage_step scenario
    spacer
    echo -e "${YELLOW}📌 Step: Select the scenario${NC}"
    # Extract top-level keys (scenarios) from the JSON
    SCENARIOS=($(echo "$WORKFLOW_JSON" | python -c "import sys, json; print(' '.join(json.load(sys.stdin).keys()))"))

    if [[ ${#SCENARIOS[@]} -eq 0 ]]; then
        echo "❌ No scenarios found in the JSON output."
        exit 1
    fi

    echo "📝 Available scenarios:"
    for i in "${!SCENARIOS[@]}"; do
        echo "$(($i + 1))) ${SCENARIOS[$i]}"
    done

    # Ask the user to select a scenario
    while true; do
        read -p "Enter the number of the scenario you want to test: " scenario_choice
        if [[ "$scenario_choice" =~ ^[0-9]+$ ]] && (( scenario_choice >= 1 && scenario_choice <= ${#SCENARIOS[@]} )); then
            export SCENARIO="${SCENARIOS[$((scenario_choice - 1))]}"
            break
        else
            echo "❌ Invalid choice. Please select a number between 1 and ${#SCENARIOS[@]}."
        fi
    done

    echo "✅ Selected scenario: $SCENARIO"
    WIZARD_SCENARIO="${SCENARIO}"
    export WIZARD_SCENARIO
}

# Select the weblog based on the chosen scenario
select_weblog() {
    wizard_usage_step weblog
    spacer
    echo -e "${YELLOW}📌 Step: Select the weblog${NC}"
    echo "🔄 Fetching weblogs for the selected scenario: $SCENARIO..."

    # Extract available weblogs - handle both list and dict formats
    # K8s lib injection returns: {scenario: [weblog1, weblog2]}
    # AWS/Docker/K8s injector dev return: {scenario: {weblog1: [...], weblog2: [...]}}
    WEBLOGS=($(echo "$WORKFLOW_JSON" | python -c "
import sys, json
data = json.load(sys.stdin)
scenario_data = data.get('$SCENARIO', {})
# Check if it's a list (K8s lib injection) or dict (AWS/Docker/K8s injector dev)
if isinstance(scenario_data, list):
    print(' '.join(scenario_data))
else:
    print(' '.join(scenario_data.keys()))
"))

    if [[ ${#WEBLOGS[@]} -eq 0 ]]; then
        echo "❌ No weblogs found for scenario: $SCENARIO"
        exit 1
    fi

    echo "📝 Available weblogs:"
    for i in "${!WEBLOGS[@]}"; do
        echo "$(($i + 1))) ${WEBLOGS[$i]}"
    done

    # Ask the user to select a weblog
    while true; do
        read -p "Enter the number of the weblog you want to test: " weblog_choice
        if [[ "$weblog_choice" =~ ^[0-9]+$ ]] && (( weblog_choice >= 1 && weblog_choice <= ${#WEBLOGS[@]} )); then
            export WEBLOG="${WEBLOGS[$((weblog_choice - 1))]}"
            break
        else
            echo "❌ Invalid choice. Please select a number between 1 and ${#WEBLOGS[@]}."
        fi
    done

    echo "✅ Selected weblog: $WEBLOG"
    WIZARD_WEBLOG="${WEBLOG}"
    export WIZARD_WEBLOG
}
