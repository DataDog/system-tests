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
# Step 1: Select AI Agent
# ============================================================================
echo -e "${MAGENTA}━━━ Step 1: Select AI Agent ━━━${NC}"
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

# ============================================================================
# Step 2: Select Test Scenarios
# ============================================================================
echo -e "${MAGENTA}━━━ Step 2: Select Test Scenarios ━━━${NC}"
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
# Step 3: Run the evaluation
# ============================================================================
echo -e "${MAGENTA}━━━ Step 3: Running Evaluation ━━━${NC}"
echo ""

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
echo -e "${BLUE}📊 Running promptfoo evaluation...${NC}"

# Run promptfoo with selected test file or all
# Note: Using -t (test file) instead of -c (config) to preserve the main config's provider settings
if [[ -n "$SELECTED_CONFIG" ]]; then
    promptfoo eval --no-cache -t "$SELECTED_CONFIG"
else
    promptfoo eval --no-cache
fi

echo ""
echo -e "${GREEN}✅ Evaluation complete!${NC}"
