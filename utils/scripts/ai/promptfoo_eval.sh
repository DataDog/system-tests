#!/bin/bash
set -euo pipefail

# Get the repository root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PROMPTFOO_DIR="$REPO_ROOT/.promptfoo"

# Colors for pretty output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║          ${YELLOW}🤖 Promptfoo Evaluation Wizard 🧙‍♂️${CYAN}               ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# Step 1: Select Provider
# ============================================================================
echo -e "${MAGENTA}━━━ Step 1: Select Provider ━━━${NC}"
echo ""
echo -e "${BLUE}Which provider would you like to use for the evaluation?${NC}"
echo ""

# Read providers from promptfooconfig.yaml
PROVIDERS=()
PROVIDER_LABELS=()

# Parse providers from the YAML config
while IFS= read -r line; do
    # Extract provider id
    if [[ $line =~ ^[[:space:]]*-[[:space:]]*id:[[:space:]]*[\'\"]*([^\'\"]*)[\'\"]* ]]; then
        provider_id="${BASH_REMATCH[1]}"
        PROVIDERS+=("$provider_id")

        # Try to get the label from the next line
        label=""
    elif [[ $line =~ ^[[:space:]]*label:[[:space:]]*[\'\"]*([^\'\"]*)[\'\"]* ]] && [[ ${#PROVIDERS[@]} -gt ${#PROVIDER_LABELS[@]} ]]; then
        label="${BASH_REMATCH[1]}"
        PROVIDER_LABELS+=("$label")
    elif [[ ${#PROVIDERS[@]} -gt ${#PROVIDER_LABELS[@]} ]]; then
        # No label found for this provider, use empty string
        PROVIDER_LABELS+=("")
    fi
done < "$REPO_ROOT/promptfooconfig.yaml"

# Ensure we have labels for all providers
while [[ ${#PROVIDER_LABELS[@]} -lt ${#PROVIDERS[@]} ]]; do
    PROVIDER_LABELS+=("")
done

num_providers=${#PROVIDERS[@]}

if [[ $num_providers -eq 0 ]]; then
    echo -e "${YELLOW}⚠️  No providers found in promptfooconfig.yaml${NC}"
    exit 1
fi

echo -e "  ${GREEN}0)${NC} Use ALL providers"
echo ""

# Display available providers
idx=1
for i in "${!PROVIDERS[@]}"; do
    provider="${PROVIDERS[$i]}"
    label="${PROVIDER_LABELS[$i]}"

    if [[ -n "$label" ]]; then
        echo -e "  ${GREEN}${idx})${NC} ${label} ${CYAN}(${provider})${NC}"
    else
        echo -e "  ${GREEN}${idx})${NC} ${provider}"
    fi
    idx=$((idx + 1))
done
echo ""

while true; do
    read -rp "Enter your choice (0-${num_providers}): " provider_choice

    # Validate input is a number
    if ! [[ "$provider_choice" =~ ^[0-9]+$ ]]; then
        echo -e "${YELLOW}⚠️  Please enter a number.${NC}"
        continue
    fi

    if [[ "$provider_choice" -eq 0 ]]; then
        SELECTED_PROVIDER=""
        USE_LOCAL_PROVIDER=false
        echo ""
        echo -e "${GREEN}✓ Selected: ${CYAN}ALL providers${NC}"
        break
    elif [[ "$provider_choice" -ge 1 && "$provider_choice" -le $num_providers ]]; then
        SELECTED_PROVIDER="${PROVIDERS[$((provider_choice - 1))]}"
        selected_label="${PROVIDER_LABELS[$((provider_choice - 1))]}"

        # Check if this is the local provider (starts with "file://")
        if [[ "$SELECTED_PROVIDER" == file://* ]]; then
            USE_LOCAL_PROVIDER=true
        else
            USE_LOCAL_PROVIDER=false
        fi

        echo ""
        if [[ -n "$selected_label" ]]; then
            echo -e "${GREEN}✓ Selected provider: ${CYAN}${selected_label} (${SELECTED_PROVIDER})${NC}"
        else
            echo -e "${GREEN}✓ Selected provider: ${CYAN}${SELECTED_PROVIDER}${NC}"
        fi
        break
    else
        echo -e "${YELLOW}⚠️  Invalid choice. Please enter a number between 0 and ${num_providers}.${NC}"
    fi
done

echo ""

# ============================================================================
# Step 2: Select AI Agent (only if local provider is selected)
# ============================================================================
if [[ "$USE_LOCAL_PROVIDER" == true ]]; then
    echo -e "${MAGENTA}━━━ Step 2: Select AI Agent ━━━${NC}"
    echo ""
    echo -e "${BLUE}Which AI agent would you like to use for the evaluation?${NC}"
    echo ""
    echo -e "  ${GREEN}1)${NC} cursor-agent  - Use Cursor AI Agent"
    echo -e "  ${GREEN}2)${NC} claude        - Use Claude CLI"
    echo ""

    while true; do
        read -rp "Enter your choice (1 or 2): " choice
        case $choice in
            1)
                AGENT="cursor-agent"
                break
                ;;
            2)
                AGENT="claude"
                break
                ;;
            *)
                echo -e "${YELLOW}⚠️  Invalid choice. Please enter 1 or 2.${NC}"
                ;;
        esac
    done

    echo ""
    echo -e "${GREEN}✓ Selected agent: ${CYAN}${AGENT}${NC}"
    echo ""
fi

# ============================================================================
# Step 3: Select Test Scenarios
# ============================================================================
echo -e "${MAGENTA}━━━ Step 3: Select Test Scenarios ━━━${NC}"
echo ""

# Find all test YAML files (portable approach for macOS/older bash)
TEST_FILES=()
while IFS= read -r file; do
    TEST_FILES+=("$file")
done < <(find "$PROMPTFOO_DIR" -maxdepth 1 -name "tests_*.yaml" -type f | sort)

num_files=${#TEST_FILES[@]}

if [[ $num_files -eq 0 ]]; then
    echo -e "${YELLOW}⚠️  No test files found in $PROMPTFOO_DIR${NC}"
    exit 1
fi

echo -e "${BLUE}Would you like to run all scenarios or select specific ones?${NC}"
echo ""
echo -e "  ${GREEN}0)${NC} Run ALL scenarios"
echo ""

# Display available test files
idx=1
for file in "${TEST_FILES[@]}"; do
    filename=$(basename "$file")
    # Remove 'tests_' prefix and '.yaml' suffix for display
    scenario_name="${filename#tests_}"
    scenario_name="${scenario_name%.yaml}"
    echo -e "  ${GREEN}${idx})${NC} ${scenario_name}"
    idx=$((idx + 1))
done
echo ""

while true; do
    read -rp "Enter your choice (0-${num_files}): " scenario_choice

    # Validate input is a number
    if ! [[ "$scenario_choice" =~ ^[0-9]+$ ]]; then
        echo -e "${YELLOW}⚠️  Please enter a number.${NC}"
        continue
    fi

    if [[ "$scenario_choice" -eq 0 ]]; then
        SELECTED_CONFIG=""
        echo ""
        echo -e "${GREEN}✓ Selected: ${CYAN}ALL scenarios${NC}"
        break
    elif [[ "$scenario_choice" -ge 1 && "$scenario_choice" -le $num_files ]]; then
        SELECTED_CONFIG="${TEST_FILES[$((scenario_choice - 1))]}"
        selected_name=$(basename "$SELECTED_CONFIG")
        selected_name="${selected_name#tests_}"
        selected_name="${selected_name%.yaml}"
        echo ""
        echo -e "${GREEN}✓ Selected scenario: ${CYAN}${selected_name}${NC}"
        break
    else
        echo -e "${YELLOW}⚠️  Invalid choice. Please enter a number between 0 and ${num_files}.${NC}"
    fi
done

echo ""

# ============================================================================
# Step 4: Run the evaluation
# ============================================================================
echo -e "${MAGENTA}━━━ Step 4: Running Evaluation ━━━${NC}"
echo ""

# Run the selected agent only if using local provider
if [[ "$USE_LOCAL_PROVIDER" == true ]]; then
    # Prepare the prompt based on selected config
    if [[ -n "$SELECTED_CONFIG" ]]; then
        AI_PROMPT="@promptfoo-llm.mdc test the file $SELECTED_CONFIG"
    else
        AI_PROMPT="@promptfoo-llm.mdc Run the complete test suite."
    fi

    # Run the selected agent
    if [[ "$AGENT" == "cursor-agent" ]]; then
        echo -e "${BLUE}🔑 Logging in to cursor-agent...${NC}"
        cursor-agent login
        echo ""
        echo -e "${BLUE}🚀 Running evaluation with cursor-agent...${NC}"
        cursor-agent -p "$AI_PROMPT"
    else
        echo -e "${BLUE}🚀 Running evaluation with claude...${NC}"
        claude --permission-mode acceptEdits -p "$AI_PROMPT"
    fi
    echo ""
fi
echo -e "${BLUE}📊 Running promptfoo evaluation...${NC}"

# Build the promptfoo command
PROMPTFOO_CMD="promptfoo eval --no-cache"

# Add test file if specific scenario was selected
if [[ -n "$SELECTED_CONFIG" ]]; then
    PROMPTFOO_CMD="$PROMPTFOO_CMD -t $SELECTED_CONFIG"
fi

# Add provider filter if specific provider was selected
if [[ -n "$SELECTED_PROVIDER" ]]; then
    PROMPTFOO_CMD="$PROMPTFOO_CMD --filter-providers $SELECTED_PROVIDER"
fi

# Run the command
eval "$PROMPTFOO_CMD"

echo ""
echo -e "${GREEN}✅ Evaluation complete!${NC}"
