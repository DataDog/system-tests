#!/bin/bash
# shellcheck disable=SC2207,SC2162,SC2206

# Function: Add blank lines for better UX
spacer() {
    echo ""
    echo "-----------------------------------------------"
    echo ""
}

echo "====================================================="
echo "🚀 Welcome to System-Tests DOCKER SSI Tests Wizard 🚀"
echo "===================================================="
echo ""

# 🎨 Colors for styling
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
CYAN='\033[1;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Welcome to the System Tests Wizard! 🔧${NC}"

# 📌 Step 1: Ask for TEST_LIBRARY
echo -e "${YELLOW}📌 Step 1: Choose the language to test${NC}"
options=("java" "python" "nodejs" "php" "dotnet")

select TEST_LIBRARY in "${options[@]}"; do
    if [[ " ${options[*]} " =~ " ${TEST_LIBRARY} " ]]; then
        echo -e "${GREEN}✅ You selected: ${TEST_LIBRARY}${NC}"
        break
    else
        echo -e "${RED}❌ Invalid option. Please select a valid language.${NC}"
    fi
done

# 📌 Step 2: Load JSON file
python utils/scripts/compute-workflow-parameters.py "$TEST_LIBRARY" -g "docker-ssi" --parametric-job-count 1 --ci-environment "prod" --format json > "/tmp/scenario_definition_${TEST_LIBRARY}.json"
JSON_FILE="/tmp/scenario_definition_${TEST_LIBRARY}.json"
if [[ ! -f "$JSON_FILE" ]]; then
    echo -e "${RED}❌ Error: JSON file '$JSON_FILE' not found!${NC}"
    exit 1
fi

echo -e "${GREEN}📄 Loaded scenario file: ${JSON_FILE}${NC}"

spacer
# 📌 Step 3: Extract scenarios
SCENARIOS=$(jq -r '.dockerssi_scenario_defs | keys[]' "$JSON_FILE")

echo -e "${YELLOW}📌 Step 3: Choose a scenario${NC}"
select SCENARIO in $SCENARIOS; do
    if [[ -n "$SCENARIO" ]]; then
        echo -e "${GREEN}✅ You selected: ${SCENARIO}${NC}"
        break
    else
        echo -e "${RED}❌ Invalid option. Please select a valid scenario.${NC}"
    fi
done
spacer
# 📌 Step 4: Extract weblogs for the chosen scenario
WEBLOGS=$(jq -r ".dockerssi_scenario_defs.${SCENARIO} | keys[]" "$JSON_FILE")

echo -e "${YELLOW}📌 Step 4: Choose a weblog${NC}"
select WEBLOG in $WEBLOGS; do
    if [[ -n "$WEBLOG" ]]; then
        echo -e "${GREEN}✅ You selected: ${WEBLOG}${NC}"
        break
    else
        echo -e "${RED}❌ Invalid option. Please select a valid weblog.${NC}"
    fi
done
spacer
# 📌 Step 5: Extract machines/images and architectures
IMAGES=($(jq -r ".dockerssi_scenario_defs.\"${SCENARIO}\".\"${WEBLOG}\" | map(keys) | add | unique | .[] | select(. != \"arch\")" "$JSON_FILE"))
ARCHS=($(jq -r ".dockerssi_scenario_defs.\"${SCENARIO}\".\"${WEBLOG}\" | map(.arch) | unique | .[]" "$JSON_FILE"))

echo -e "${YELLOW}📌 Step 5: Choose a machine/image${NC}"
select BASE_IMAGE in "${IMAGES[@]}"; do
    if [[ -n "$BASE_IMAGE" ]]; then
        echo -e "${GREEN}✅ You selected: ${BASE_IMAGE}${NC}"
        break
    else
        echo -e "${RED}❌ Invalid option. Please select a valid image.${NC}"
    fi
done

echo -e "${YELLOW}📌 Step 6: Choose an architecture${NC}"
select ARCH in "${ARCHS[@]}"; do
    if [[ -n "$ARCH" ]]; then
        echo -e "${GREEN}✅ You selected: ${ARCH}${NC}"
        break
    else
        echo -e "${RED}❌ Invalid option. Please select a valid architecture.${NC}"
    fi
done
spacer
# 📌 Step 7: Select Runtime Version (if available)
RUNTIMES=($(jq -r ".dockerssi_scenario_defs.\"${SCENARIO}\".\"${WEBLOG}\"[]
    | select(.arch == \"${ARCH}\")
    | select(has(\"${BASE_IMAGE}\"))
    | .\"${BASE_IMAGE}\"[]?" "$JSON_FILE"))
if [[ ${#RUNTIMES[@]} -gt 0 ]]; then
    echo -e "${YELLOW}📌 Step 7: Choose a runtime version ${NC}"
    select INSTALLABLE_RUNTIME in "${RUNTIMES[@]}"; do
        if [[ -n "$INSTALLABLE_RUNTIME" ]]; then
            echo -e "${GREEN}✅ You selected: ${INSTALLABLE_RUNTIME}${NC}"
            break
        else
            echo -e "${RED}❌ Invalid option.${NC}"
        fi
    done
else
    INSTALLABLE_RUNTIME=""
    echo -e "${CYAN}ℹ️  No runtime versions available. Skipping...${NC}"
fi
spacer
# 📌 Step 8: Select environment
echo -e "${YELLOW}📌 Step 8: Choose the environment${NC}"
echo "1) prod - Test latest releases of injector and tracer components (default)"
echo "2) dev - Test latest snapshots of injector and tracer components"

    # Set default value
    CI_ENVIRONMENT="prod"

    # Ask for user choice
    read -p "Enter your choice (1 for prod, 2 for dev) [default: prod]: " env_choice

    case "$env_choice" in
        1|"") CI_ENVIRONMENT="prod";;
        2) CI_ENVIRONMENT="dev";;
        *) echo "❌ Invalid choice. Defaulting to 'prod'."; CI_ENVIRONMENT="prod";;
    esac

    export CI_ENVIRONMENT
    echo "✅ Selected environment: $CI_ENVIRONMENT"

spacer
# 📌 Step 9: Optional parameters
 echo "🛠️ Optional: Use a custom version of the tracer or injector OCI image."

    # Ask for DD_INSTALLER_LIBRARY_VERSION
    read -p "Enter a custom tracer OCI image version (pipeline-<your pipeline id>) or press Enter to skip: " SSI_LIBRARY_VERSION
    if [[ -n "$SSI_LIBRARY_VERSION" ]]; then
        echo "✅ Using custom tracer OCI image version: $SSI_LIBRARY_VERSION"
    else
        echo "✅ No custom tracer OCI image version set."
    fi

    # Ask for DD_INSTALLER_INJECTOR_VERSION
    read -p "Enter a custom injector OCI image version (pipeline-<your pipeline id>) or press Enter to skip: " SSI_INJECTOR_VERSION
    if [[ -n "$SSI_INJECTOR_VERSION" ]]; then
        export DD_INSTALLER_INJECTOR_VERSION="$SSI_INJECTOR_VERSION"
        echo "✅ Using custom injector OCI image version: $SSI_INJECTOR_VERSION"
    else
        echo "✅ No custom injector OCI image version set."
    fi


# 🔹 Construct the command
CMD=("./run.sh" "$SCENARIO" "--ssi-weblog" "$WEBLOG" "--ssi-library" "$TEST_LIBRARY" "--ssi-base-image" "$BASE_IMAGE" "--ssi-arch" "$ARCH" "--ssi-env" "$CI_ENVIRONMENT")

if [[ -n "$INSTALLABLE_RUNTIME" ]]; then
    CMD+=("--ssi-installable-runtime" "$INSTALLABLE_RUNTIME")
fi

if [[ -n "$SSI_LIBRARY_VERSION" ]]; then
    CMD+=("--ssi-library-version" "$SSI_LIBRARY_VERSION")
fi

if [[ -n "$SSI_INJECTOR_VERSION" ]]; then
    CMD+=("--ssi-injector-version" "$SSI_INJECTOR_VERSION")
fi
spacer
# 📌 Step 10: Confirm and execute
    echo ""
    echo "==============================================="
    echo "🚀 READY TO RUN THE TESTS! 🚀"
    echo "==============================================="
    echo ""
    echo "✨ Here’s a summary of your selections:"
    echo "   🔹 Scenario:         $SCENARIO"
    echo "   🔹 Weblog:           $WEBLOG"
    echo "   🔹 Base Image:       $BASE_IMAGE"
    echo "   🔹 Base Image arcy:  $ARCH"
    echo "   🔹 Language runtime: $INSTALLABLE_RUNTIME"
    echo "   🔹 Environment:      $CI_ENVIRONMENT"
    echo "   🔹 Test Library:     $TEST_LIBRARY"
    echo ""

    if [[ -n "$SSI_LIBRARY_VERSION" ]]; then
        echo "   🔹 Custom Tracer OCI Image:   $SSI_LIBRARY_VERSION"
    else
        echo "   🔹 Custom Tracer OCI Image:   (Not set)"
    fi

    if [[ -n "$SSI_INJECTOR_VERSION" ]]; then
        echo "   🔹 Custom Injector OCI Image: $SSI_INJECTOR_VERSION"
    else
        echo "   🔹 Custom Injector OCI Image: (Not set)"
    fi

    echo ""
    echo "✅ Everything is set up! Here is the command that will be executed:"
    echo ""

echo -e "${GREEN}${CMD[*]}${NC}\n"

read -p "⚠️  Do you want to execute the command? (y/n): " CONFIRM
if [[ "$CONFIRM" == "y" ]]; then
    echo -e "${GREEN}▶️ Executing the command...${NC}"
    "${CMD[@]}"
else
    echo -e "${RED}❌ Execution canceled.${NC}"
fi
