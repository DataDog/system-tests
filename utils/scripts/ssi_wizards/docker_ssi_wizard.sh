#!/bin/bash
# shellcheck disable
#This script was generated using chatgpt

source utils/scripts/ssi_wizards/common_wizard_functions.sh

select_base_image_and_arch2(){
    spacer
    # 📌 Step 5: Extract machines/images and architectures
    IMAGES=($(jq -r ".dockerssi_scenario_defs.\"${SCENARIO}\".\"${WEBLOG}\" | map(keys) | add | unique | .[] | select(. != \"arch\")" "$JSON_FILE"))
    ARCHS=($(jq -r ".dockerssi_scenario_defs.\"${SCENARIO}\".\"${WEBLOG}\" | map(.arch) | unique | .[]" "$JSON_FILE"))

    echo -e "${YELLOW}📌 Step: Choose a machine/image${NC}"
    select BASE_IMAGE in "${IMAGES[@]}"; do
        if [[ -n "$BASE_IMAGE" ]]; then
            echo -e "${GREEN}✅ You selected: ${BASE_IMAGE}${NC}"
            break
        else
            echo -e "${RED}❌ Invalid option. Please select a valid image.${NC}"
        fi
    done

    echo -e "${YELLOW}📌 Step: Choose an architecture${NC}"
    select ARCH in "${ARCHS[@]}"; do
        if [[ -n "$ARCH" ]]; then
            echo -e "${GREEN}✅ You selected: ${ARCH}${NC}"
            break
        else
            echo -e "${RED}❌ Invalid option. Please select a valid architecture.${NC}"
        fi
    done
}
select_base_image_and_arch() {
    spacer
    echo -e "${YELLOW}📌 Step: Select the base image ${NC}"
    echo "🔄 Fetching available base images for:"
    echo "   - Test Library: $TEST_LIBRARY"
    echo "   - Scenario: $SCENARIO"
    echo "   - Weblog: $WEBLOG"
    echo ""

    # Extract available cluster agent (third-level keys under TEST_LIBRARY > SCENARIO > WEBLOG)
    BASE_IMAGES=($(echo "$WORKFLOW_JSON" | python -c "
import sys, json
data = json.load(sys.stdin)
base_images = data.get('$SCENARIO', {}).get('$WEBLOG', [])
print(' '.join(base_images))
"))

    if [[ ${#CLUSTER_AGENTS[@]} -eq 0 ]]; then
        echo "❗No cluster agents supported for:"
        echo "   - Test Library: $TEST_LIBRARY"
        echo "   - Scenario: $SCENARIO"
        echo "   - Weblog: $WEBLOG"
    else

        echo "📝 Available cluster agents:"
        for i in "${!CLUSTER_AGENTS[@]}"; do
            echo "$(($i + 1))) ${CLUSTER_AGENTS[$i]}"
        done

        # Ask the user to select a cluster agent
        while true; do
            read -p "Enter the number of the cluster agent you want to use: " vm_choice
            if [[ "$vm_choice" =~ ^[0-9]+$ ]] && (( vm_choice >= 1 && vm_choice <= ${#CLUSTER_AGENTS[@]} )); then
                export CLUSTER_AGENT="${CLUSTER_AGENTS[$((vm_choice - 1))]}"
                break
            else
                echo "❌ Invalid choice. Please select a number between 1 and ${#CLUSTER_AGENTS[@]}."
            fi
        done
        echo "✅ Selected cluster agent: $CLUSTER_AGENT"
    fi

}
select_runtime_version(){
    spacer
    # 📌 Step 7: Select Runtime Version (if available)
    RUNTIMES=($(jq -r ".dockerssi_scenario_defs.\"${SCENARIO}\".\"${WEBLOG}\"[]
        | select(.arch == \"${ARCH}\")
        | select(has(\"${BASE_IMAGE}\"))
        | .\"${BASE_IMAGE}\"[]?" "$JSON_FILE"))
    if [[ ${#RUNTIMES[@]} -gt 0 ]]; then
        echo -e "${YELLOW}📌 Step: Choose a runtime version ${NC}"
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
}
select_environment(){
    spacer
    # 📌 Step: Select environment
    echo -e "${YELLOW}📌 Step: Choose the environment${NC}"
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
}
select_optional_params(){
    spacer
    # 📌 Step : Optional parameters
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
}
run_the_tests(){
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
}

welcome "Docker SSI Tests"
ask_load_requirements
ask_load_k8s_requirements
ask_for_test_language
load_workflow_data "docker-ssi" "dockerssi_scenario_defs"
select_scenario
select_weblog
#select_base_image_and_arch
#select_runtime_version
#select_environment
#select_optional_params
#run_the_tests