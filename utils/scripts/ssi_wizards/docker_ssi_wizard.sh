#!/bin/bash
# shellcheck disable=all
#This script was generated using chatgpt

source utils/scripts/ssi_wizards/common_wizard_functions.sh


select_base_image_and_arch() {
    spacer
    echo -e "${YELLOW}📌 Step: Select the base image ${NC}"
    echo "🔄 Fetching available base images for:"
    echo "   - Test Library: $TEST_LIBRARY"
    echo "   - Scenario: $SCENARIO"
    echo "   - Weblog: $WEBLOG"
    echo ""

    # Extract available cluster agent (third-level keys under TEST_LIBRARY > SCENARIO > WEBLOG)


BASE_IMAGES_RAW=$(python - <<EOF
import json
import sys

# Read JSON from environment variable
json_data = '''$WORKFLOW_JSON'''

# Parse JSON
data = json.loads(json_data)
base_images = data.get('''$SCENARIO''', {}).get('''$WEBLOG''',[])
# Extract first key and concatenate with the "arch" value
first_keys_with_arch = [
    f"{list(d.keys())[0]}({d.get('arch', 'N/A')})" for d in base_images
]

# Print output
print(" ".join(first_keys_with_arch))
EOF
)
    # Convert the string into an array by splitting on spaces
    IFS=' ' read -r -a BASE_IMAGES <<< "$BASE_IMAGES_RAW"


    if [[ ${#BASE_IMAGES[@]} -eq 0 ]]; then
        echo "❗No base images supported for:"
        echo "   - Test Library: $TEST_LIBRARY"
        echo "   - Scenario: $SCENARIO"
        echo "   - Weblog: $WEBLOG"
        exit 1
    else

        echo "📝 Available base images:"
        for i in "${!BASE_IMAGES[@]}"; do
            echo "$(($i + 1))) ${BASE_IMAGES[$i]}"
        done

        # Ask the user to select a base image
        while true; do
            read -p "Enter the number of the base image you want to use: " vm_choice
            if [[ "$vm_choice" =~ ^[0-9]+$ ]] && (( vm_choice >= 1 && vm_choice <= ${#BASE_IMAGES[@]} )); then
                export BASE_IMAGE_RAW="${BASE_IMAGES[$((vm_choice - 1))]}"
                break
            else
                echo "❌ Invalid choice. Please select a number between 1 and ${#BASE_IMAGES[@]}."
            fi
        done

        # Extracting values using parameter expansion
        BASE_IMAGE="${BASE_IMAGE_RAW%%(*}"  # Everything before '('
        ARCH="${BASE_IMAGE_RAW##*(}"        # Everything after '(' and remove ')'

        # Remove trailing ')'
        ARCH="${ARCH%)}"

        # Get the current laptop architecture
        LAPTOP_ARCH=$(uname -m)

        # Normalize architecture names for comparison
        normalize_arch() {
            local arch="$1"
            # Remove linux/ prefix if present
            arch="${arch#linux/}"
            case "$arch" in
                "x86_64"|"amd64") echo "amd64" ;;
                "arm64"|"aarch64") echo "arm64" ;;
                *) echo "$arch" ;;
            esac
        }

        NORMALIZED_LAPTOP_ARCH=$(normalize_arch "$LAPTOP_ARCH")
        NORMALIZED_SELECTED_ARCH=$(normalize_arch "$ARCH")

        # Show warning if architectures don't match
        if [[ "$NORMALIZED_LAPTOP_ARCH" != "$NORMALIZED_SELECTED_ARCH" ]]; then
            echo ""
            echo -e "${RED}⚠️  WARNING: Architecture Mismatch Detected! ⚠️${NC}"
            echo -e "${YELLOW}   Your laptop architecture: $LAPTOP_ARCH ($NORMALIZED_LAPTOP_ARCH)${NC}"
            echo -e "${YELLOW}   Selected test architecture: $ARCH ($NORMALIZED_SELECTED_ARCH)${NC}"
            echo ""
            echo -e "${CYAN}ℹ️  Note: Running tests with different architecture may:${NC}"
            echo -e "${CYAN}   • Take longer due to emulation${NC}"
            echo -e "${CYAN}   • Have different performance characteristics${NC}"
            echo -e "${CYAN}   • Potentially encounter architecture-specific issues${NC}"
            echo ""
            read -p "Do you want to continue with this architecture? (y/n): " arch_confirm
            if [[ "$arch_confirm" != "y" ]]; then
                echo -e "${RED}❌ Architecture selection canceled. Please choose a different base image.${NC}"
                select_base_image_and_arch
                return
            fi
            echo -e "${GREEN}✅ Continuing with selected architecture: $ARCH${NC}"
        fi

        echo "✅ Selected base image: $BASE_IMAGE ($ARCH)"
    fi

}

select_runtime_version(){

    output=$(python - <<EOF
import json
import os

# Read JSON from environment variable
json_data = os.getenv("WORKFLOW_JSON", "[]")
# Ensure JSON is parsed correctly
try:
    data = json.loads(json_data)
    data = data[os.getenv("SCENARIO", "NAIS")]
    data = data[os.getenv("WEBLOG", "NONONON")]
except json.JSONDecodeError:
    print("")
    exit(1)

# Find the dictionary where "arch" matches the selected ARCH
selected_entry = next((d for d in data if isinstance(d, dict) and d.get("arch") == "$ARCH"), None)

# Extract the array from the first key (excluding "arch")
if selected_entry:
    first_key = next((k for k in selected_entry.keys() if k != "arch"), None)
    result = selected_entry.get(first_key, [])
else:
    result = []

# Print the array as a space-separated string for Bash
print(" ".join(result))
EOF
)

    # Convert output into an array
    IFS=' ' read -r -a RUNTIMES <<< "$output"

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
    echo ""
    echo -e "${YELLOW}⚠️  Important Warning About Pipeline IDs:${NC}"
    echo -e "${CYAN}   If the pipeline-id reference is not correct, you may encounter runtime errors${NC}"
    echo -e "${CYAN}   related to registry access. However, the real problem is usually that:${NC}"
    echo -e "${CYAN}   • The pipeline-id doesn't exist${NC}"
    echo -e "${CYAN}   • The pipeline-id doesn't contain the required OCI images${NC}"
    echo -e "${CYAN}   Make sure your pipeline-id is valid and contains the built images.${NC}"
    echo ""

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
        echo "✨ Here's a summary of your selections:"
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

configure_private_registry() {
    spacer
    echo -e "${YELLOW}📌 Step: Configure Private Registry (not mandatory) ${NC}"
    read -p "Do you want to configure a private registry? (y/n) [default: n]: " configure_choice
    configure_choice=${configure_choice:-n}
    if [[ "$configure_choice" != "y" ]]; then
        echo -e "${CYAN}ℹ️  Skipping private registry configuration. Using Docker Hub or public images.${NC}"
        return
    fi
    echo "Please select one of the following options:"
    echo "1) Use existing ECR registry (235494822917.dkr.ecr.us-east-1.amazonaws.com)"
    echo "2) Configure your own registry"
    read -p "Enter your choice (1 or 2): " registry_choice
    if [[ "$registry_choice" == "1" ]]; then
        echo "Configuring ECR registry..."
        export PRIVATE_DOCKER_REGISTRY="235494822917.dkr.ecr.us-east-1.amazonaws.com"
        export PRIVATE_DOCKER_REGISTRY_USER="AWS"
        aws-vault exec sso-apm-ecosystems-reliability-account-admin -- aws ecr get-login-password | docker login --username AWS --password-stdin 235494822917.dkr.ecr.us-east-1.amazonaws.com
        export PRIVATE_DOCKER_REGISTRY_TOKEN=$(aws-vault exec sso-apm-ecosystems-reliability-account-admin -- aws ecr get-login-password --region us-east-1)
        echo -e "${GREEN}✅ ECR registry configured and logged in successfully.${NC}"
    elif [[ "$registry_choice" == "2" ]]; then
        read -p "Enter your registry URL: " PRIVATE_DOCKER_REGISTRY
        read -p "Enter your registry username: " PRIVATE_DOCKER_REGISTRY_USER
        read -sp "Enter your registry token/password: " PRIVATE_DOCKER_REGISTRY_TOKEN
        echo
        export PRIVATE_DOCKER_REGISTRY
        export PRIVATE_DOCKER_REGISTRY_USER
        export PRIVATE_DOCKER_REGISTRY_TOKEN
        echo "Logging in to custom registry..."
        echo "$PRIVATE_DOCKER_REGISTRY_TOKEN" | docker login --username "$PRIVATE_DOCKER_REGISTRY_USER" --password-stdin "$PRIVATE_DOCKER_REGISTRY"
        if [[ $? -eq 0 ]]; then
            echo -e "${GREEN}✅ Custom registry configured and logged in successfully.${NC}"
        else
            echo -e "${RED}❌ Failed to login to custom registry.${NC}"
        fi
    else
        echo -e "${RED}❌ Invalid choice. Please select 1 or 2.${NC}"
        configure_private_registry
    fi
}

welcome "Docker SSI Tests"
ask_load_requirements
configure_private_registry
ask_for_test_language
load_workflow_data "docker-ssi" "dockerssi_scenario_defs"
select_scenario
select_weblog
select_base_image_and_arch
select_runtime_version
select_environment
select_optional_params
run_the_tests