#!/bin/bash
# shellcheck disable=all
#This script was generated using chatgpt

source utils/scripts/ssi_wizards/common_wizard_functions.sh

# Constants
readonly AWS_ECR_ACCOUNT="apm-ecosystems-reliability"

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

ask_load_k8s_requirements(){
    # 📌 Step: Ask user for Kubernetes provider
    echo -e "${YELLOW}📌 Step: Choose a Kubernetes provider${NC}"
    select K8S_PROVIDER in "minikube" "kind"; do
        if [[ -n "$K8S_PROVIDER" ]]; then
            echo -e "${GREEN}✅ You selected: ${K8S_PROVIDER}${NC}"
            break
        else
            echo -e "${RED}❌ Invalid option. Please select minikube or kind.${NC}"
        fi
    done

    # 📌 Step: Install Kubernetes provider if not present
    if [[ "$K8S_PROVIDER" == "kind" ]]; then
        if ! command_exists kind; then
            read -p "⚠️  Kind is not installed. Do you want to install it? (y/n): " INSTALL_KIND
            if [[ "$INSTALL_KIND" == "y" ]]; then
                echo "Installing Kind..."
                KIND_VERSION='v0.17.0'
                # Download appropriate version (Mac M1 arm64 arch or linux amd64)
                ARCH=$(uname -m | sed 's/x86_//;s/i[3-6]86/32/')
                if [ "$ARCH" = "arm64" ]; then
                    curl -Lo ./kind https://github.com/kubernetes-sigs/kind/releases/download/$KIND_VERSION/kind-darwin-arm64
                else
                    curl -Lo ./kind https://kind.sigs.k8s.io/dl/$KIND_VERSION/kind-linux-amd64
                fi
                chmod +x ./kind
                sudo mv ./kind /usr/local/bin/kind
                echo -e "${GREEN}✅ Kind installed successfully.${NC}"
            fi
        fi
    elif [[ "$K8S_PROVIDER" == "minikube" ]]; then
        if ! command_exists minikube; then
            read -p "⚠️  Minikube is not installed. Do you want to install it? (y/n): " INSTALL_MINIKUBE
            if [[ "$INSTALL_MINIKUBE" == "y" ]]; then
                echo "Installing Minikube..."
                ARCH=$(uname -m)
                if [[ "$ARCH" == "arm64" ]]; then
                    curl -LO https://github.com/kubernetes/minikube/releases/latest/download/minikube-darwin-arm64
                    sudo install minikube-darwin-arm64 /usr/local/bin/minikube
                elif [[ "$ARCH" == "x86_64" ]]; then
                    curl -LO https://github.com/kubernetes/minikube/releases/latest/download/minikube-linux-amd64
                    sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64
                fi
                echo -e "${GREEN}✅ Minikube installed successfully.${NC}"
            fi
        fi
    fi

    # 📌 Step: Install Helm if not present
    if ! command_exists helm; then
        read -p "⚠️  Helm is not installed. Do you want to install it? (y/n): " INSTALL_HELM
        if [[ "$INSTALL_HELM" == "y" ]]; then
            echo "Installing Helm..."
            curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
            if command_exists helm; then
                echo -e "${GREEN}✅ Helm installed successfully.${NC}"
            else
                echo -e "${RED}❌ Helm installation failed.${NC}"
            fi
        fi
    else
        echo -e "${GREEN}✅ Helm is already installed ($(helm version --short))${NC}"
    fi
}

configure_private_registry() {
    spacer
    echo -e "${YELLOW}📌 Step: Configure Private Registry${NC}"
    echo "Configuring ECR registry (235494822917.dkr.ecr.us-east-1.amazonaws.com)..."

    export PRIVATE_DOCKER_REGISTRY="235494822917.dkr.ecr.us-east-1.amazonaws.com"
    export PRIVATE_DOCKER_REGISTRY_USER="AWS"

    # Login to ECR and get token
    aws-vault exec "sso-${AWS_ECR_ACCOUNT}-account-admin" -- aws ecr get-login-password | docker login --username AWS --password-stdin 235494822917.dkr.ecr.us-east-1.amazonaws.com
    export PRIVATE_DOCKER_REGISTRY_TOKEN=$(aws-vault exec "sso-${AWS_ECR_ACCOUNT}-account-admin" -- aws ecr get-login-password --region us-east-1)

    echo -e "${GREEN}✅ ECR registry configured successfully.${NC}"
}

select_weblog_img(){
    spacer
    echo -e "${YELLOW}📌 Step: Select Weblog Image${NC}"
    echo ""
    echo -e "${CYAN}ℹ️  K8s lib injection tests use weblog images from the private registry (ECR).${NC}"
    echo ""
    echo "You have two options:"
    echo "  1️⃣  Use an existing weblog image from the registry (default: ${WEBLOG}:latest)"
    echo "  2️⃣  Build and push your local weblog to the registry with a custom tag"
    echo ""

    WEBLOG_IMAGE="$PRIVATE_DOCKER_REGISTRY/system-tests/$WEBLOG:latest"

    # Ask if user wants to build and push the weblog
    read -p "Do you want to build and push your local weblog? (y/n): " BUILD_WEBLOG
    if [[ "$BUILD_WEBLOG" == "y" ]]; then
        echo ""
        echo -e "${YELLOW}⚠️  Important: Using 'latest' tag might impact CI as it uses 'latest' by default.${NC}"
        echo "💡 Recommendation: Use a unique tag (e.g., v1.0.0, test-feature, your-name-test)"
        echo ""
        read -p "Enter tag name for the weblog: " TAG_NAME

        if [[ -z "$TAG_NAME" ]]; then
            echo -e "${RED}❌ Tag name cannot be empty.${NC}"
            select_weblog_img
            return
        fi

        echo ""
        echo "🔨 Building and pushing weblog to ${PRIVATE_DOCKER_REGISTRY}/system-tests/${WEBLOG}:${TAG_NAME}..."
        ./lib-injection/build/build_lib_injection_weblog.sh -w "${WEBLOG}" -l "${TEST_LIBRARY}" \
            --push-tag "${PRIVATE_DOCKER_REGISTRY}/system-tests/${WEBLOG}:${TAG_NAME}" \
            --docker-platform linux/arm64,linux/amd64

        if [[ $? -eq 0 ]]; then
            echo -e "${GREEN}✅ Weblog built and pushed successfully.${NC}"
            WEBLOG_IMAGE="${PRIVATE_DOCKER_REGISTRY}/system-tests/${WEBLOG}:${TAG_NAME}"
        else
            echo -e "${RED}❌ Failed to build and push weblog.${NC}"
            read -p "Do you want to continue with the existing image from registry? (y/n): " CONTINUE
            if [[ "$CONTINUE" != "y" ]]; then
                echo -e "${RED}❌ Exiting...${NC}"
                exit 1
            fi
        fi
    fi

    echo ""
    echo "📦 Select the weblog image to use for testing:"
    select option in "${WEBLOG_IMAGE}" "Use custom image"; do
        if [[ -n "$option" ]]; then
            if [[ "$option" == "Use custom image" ]]; then
                read -p "Enter custom weblog image (e.g., ${PRIVATE_DOCKER_REGISTRY}/system-tests/${WEBLOG}:my-tag): " WEBLOG_IMAGE
            else
                WEBLOG_IMAGE="$option"
            fi
            break
        fi
    done

    echo -e "${GREEN}✅ Selected weblog image: ${WEBLOG_IMAGE}${NC}"
}

select_cluster_agent() {
    spacer
    echo -e "${YELLOW}📌 Step: Select the cluster agent${NC}"
    echo "🔄 Fetching available cluster agent images..."
    echo ""

    # Use K8sComponentsParser to get cluster agent versions
    CLUSTER_AGENTS=($(python -c "
from utils.k8s.k8s_components_parser import K8sComponentsParser
parser = K8sComponentsParser()
versions = parser.get_all_component_versions('cluster_agent')
print(' '.join(versions))
"))

    if [[ ${#CLUSTER_AGENTS[@]} -eq 0 ]]; then
        echo "❗No cluster agents found in configuration."
        read -p "Enter custom cluster agent image: " CLUSTER_AGENT
    else
        echo "📝 Available cluster agents:"
        for i in "${!CLUSTER_AGENTS[@]}"; do
            echo "$(($i + 1))) ${CLUSTER_AGENTS[$i]}"
        done
        echo "$((${#CLUSTER_AGENTS[@]} + 1))) Use custom image"

        # Ask the user to select a cluster agent
        while true; do
            read -p "Enter the number of the cluster agent you want to use: " vm_choice
            if [[ "$vm_choice" =~ ^[0-9]+$ ]] && (( vm_choice >= 1 && vm_choice <= ${#CLUSTER_AGENTS[@]} + 1 )); then
                if (( vm_choice == ${#CLUSTER_AGENTS[@]} + 1 )); then
                    read -p "Enter custom cluster agent image: " CLUSTER_AGENT
                else
                    export CLUSTER_AGENT="${CLUSTER_AGENTS[$((vm_choice - 1))]}"
                fi
                break
            else
                echo "❌ Invalid choice. Please select a number between 1 and $((${#CLUSTER_AGENTS[@]} + 1))."
            fi
        done
        echo "✅ Selected cluster agent: $CLUSTER_AGENT"
    fi
}

select_helm_chart_version(){
    spacer
    echo -e "${YELLOW}📌 Step: Configure Helm Chart Version${NC}"
    echo "🔄 Fetching available helm chart versions..."
    echo ""

    # Check if this is an OPERATOR scenario
    if [[ "$SCENARIO" == *"OPERATOR"* ]]; then
        # Use K8sComponentsParser to get helm chart operator versions
        HELM_CHART_OPERATOR_VERSIONS=($(python -c "
from utils.k8s.k8s_components_parser import K8sComponentsParser
parser = K8sComponentsParser()
versions = parser.get_all_component_versions('helm_chart_operator')
print(' '.join(versions))
"))

        if [[ ${#HELM_CHART_OPERATOR_VERSIONS[@]} -gt 0 ]]; then
            echo "📝 Available Helm Chart Operator versions:"
            for i in "${!HELM_CHART_OPERATOR_VERSIONS[@]}"; do
                echo "$(($i + 1))) ${HELM_CHART_OPERATOR_VERSIONS[$i]}"
            done
            echo "$((${#HELM_CHART_OPERATOR_VERSIONS[@]} + 1))) Use custom version"

            while true; do
                read -p "Enter the number of the Helm Chart Operator version you want to use: " chart_choice
                if [[ "$chart_choice" =~ ^[0-9]+$ ]] && (( chart_choice >= 1 && chart_choice <= ${#HELM_CHART_OPERATOR_VERSIONS[@]} + 1 )); then
                    if (( chart_choice == ${#HELM_CHART_OPERATOR_VERSIONS[@]} + 1 )); then
                        read -p "Enter custom Helm Chart Operator version: " K8S_HELM_CHART_OPERATOR
                    else
                        K8S_HELM_CHART_OPERATOR="${HELM_CHART_OPERATOR_VERSIONS[$((chart_choice - 1))]}"
                    fi
                    export K8S_HELM_CHART_OPERATOR
                    break
                else
                    echo "❌ Invalid choice. Please select a number between 1 and $((${#HELM_CHART_OPERATOR_VERSIONS[@]} + 1))."
                fi
            done
            echo "✅ Selected Helm Chart Operator version: $K8S_HELM_CHART_OPERATOR"
            return
        fi
    else
        # Use K8sComponentsParser to get regular helm chart versions
        HELM_CHART_VERSIONS=($(python -c "
from utils.k8s.k8s_components_parser import K8sComponentsParser
parser = K8sComponentsParser()
versions = parser.get_all_component_versions('helm_chart')
print(' '.join(versions))
"))

        if [[ ${#HELM_CHART_VERSIONS[@]} -gt 0 ]]; then
            echo "📝 Available Helm Chart versions:"
            for i in "${!HELM_CHART_VERSIONS[@]}"; do
                echo "$(($i + 1))) ${HELM_CHART_VERSIONS[$i]}"
            done
            echo "$((${#HELM_CHART_VERSIONS[@]} + 1))) Use custom version"

            while true; do
                read -p "Enter the number of the Helm Chart version you want to use: " chart_choice
                if [[ "$chart_choice" =~ ^[0-9]+$ ]] && (( chart_choice >= 1 && chart_choice <= ${#HELM_CHART_VERSIONS[@]} + 1 )); then
                    if (( chart_choice == ${#HELM_CHART_VERSIONS[@]} + 1 )); then
                        read -p "Enter custom Helm Chart version: " K8S_HELM_CHART
                    else
                        K8S_HELM_CHART="${HELM_CHART_VERSIONS[$((chart_choice - 1))]}"
                    fi
                    export K8S_HELM_CHART
                    break
                else
                    echo "❌ Invalid choice. Please select a number between 1 and $((${#HELM_CHART_VERSIONS[@]} + 1))."
                fi
            done
            echo "✅ Selected Helm Chart version: $K8S_HELM_CHART"
            return
        fi
    fi

    # No helm charts found
    echo -e "${CYAN}ℹ️  No helm chart versions defined, using default.${NC}"
}

select_lib_init_and_injector(){
    spacer
    echo -e "${YELLOW}📌 Step: Configure Lib Init Image${NC}"
    echo "🔄 Fetching available lib-init images for $TEST_LIBRARY..."
    echo ""

    # Use K8sComponentsParser to get lib_init versions for the selected language
    LIB_INIT_IMAGES=($(python -c "
from utils.k8s.k8s_components_parser import K8sComponentsParser
parser = K8sComponentsParser()
versions = parser.get_all_component_versions('lib_init', '$TEST_LIBRARY')
print(' '.join(versions))
"))

    if [[ ${#LIB_INIT_IMAGES[@]} -eq 0 ]]; then
        echo "❗No lib-init images found for $TEST_LIBRARY."
        read -p "Enter custom lib-init image: " K8S_LIB_INIT_IMG
    else
        echo "📝 Available lib-init images:"
        for i in "${!LIB_INIT_IMAGES[@]}"; do
            echo "$(($i + 1))) ${LIB_INIT_IMAGES[$i]}"
        done
        echo "$((${#LIB_INIT_IMAGES[@]} + 1))) Use custom image"

        while true; do
            read -p "Enter the number of the lib-init image you want to use: " lib_init_choice
            if [[ "$lib_init_choice" =~ ^[0-9]+$ ]] && (( lib_init_choice >= 1 && lib_init_choice <= ${#LIB_INIT_IMAGES[@]} + 1 )); then
                if (( lib_init_choice == ${#LIB_INIT_IMAGES[@]} + 1 )); then
                    read -p "Enter custom lib-init image: " K8S_LIB_INIT_IMG
                else
                    K8S_LIB_INIT_IMG="${LIB_INIT_IMAGES[$((lib_init_choice - 1))]}"
                fi
                break
            else
                echo "❌ Invalid choice. Please select a number between 1 and $((${#LIB_INIT_IMAGES[@]} + 1))."
            fi
        done
    fi
    echo "✅ Selected lib-init image: $K8S_LIB_INIT_IMG"

    # Check if scenario uses cluster agents (NO_AC scenarios don't)
    if [[ -z "$CLUSTER_AGENT" || "$CLUSTER_AGENT" == "''" ]]; then
        echo -e "${CYAN}ℹ️  No cluster agent found, skipping injector configuration.${NC}"
        K8S_INJECTOR_IMG="''"
        CLUSTER_AGENT="''"
    else
        spacer
        echo -e "${YELLOW}📌 Step: Configure Injector Image${NC}"
        echo "🔄 Fetching available injector images..."
        echo ""

        # Use K8sComponentsParser to get injector versions
        INJECTOR_IMAGES=($(python -c "
from utils.k8s.k8s_components_parser import K8sComponentsParser
parser = K8sComponentsParser()
versions = parser.get_all_component_versions('injector')
print(' '.join(versions))
"))

        if [[ ${#INJECTOR_IMAGES[@]} -eq 0 ]]; then
            echo "❗No injector images found."
            read -p "Enter custom injector image: " K8S_INJECTOR_IMG
        else
            echo "📝 Available injector images:"
            for i in "${!INJECTOR_IMAGES[@]}"; do
                echo "$(($i + 1))) ${INJECTOR_IMAGES[$i]}"
            done
            echo "$((${#INJECTOR_IMAGES[@]} + 1))) Use custom image"

            while true; do
                read -p "Enter the number of the injector image you want to use: " injector_choice
                if [[ "$injector_choice" =~ ^[0-9]+$ ]] && (( injector_choice >= 1 && injector_choice <= ${#INJECTOR_IMAGES[@]} + 1 )); then
                    if (( injector_choice == ${#INJECTOR_IMAGES[@]} + 1 )); then
                        read -p "Enter custom injector image: " K8S_INJECTOR_IMG
                    else
                        K8S_INJECTOR_IMG="${INJECTOR_IMAGES[$((injector_choice - 1))]}"
                    fi
                    break
                else
                    echo "❌ Invalid choice. Please select a number between 1 and $((${#INJECTOR_IMAGES[@]} + 1))."
                fi
            done
        fi
        echo "✅ Selected injector image: $K8S_INJECTOR_IMG"
    fi
}

set_default_component_versions() {
    # Use K8sComponentsParser to set default values for all components
    echo "📦 Loading default component versions..."

    # Set default cluster agent
    CLUSTER_AGENT=$(python -c "
from utils.k8s.k8s_components_parser import K8sComponentsParser
parser = K8sComponentsParser()
print(parser.get_default_component_version('cluster_agent'))
")

    # Set default helm chart or helm chart operator based on scenario
    if [[ "$SCENARIO" == *"OPERATOR"* ]]; then
        K8S_HELM_CHART_OPERATOR=$(python -c "
from utils.k8s.k8s_components_parser import K8sComponentsParser
parser = K8sComponentsParser()
print(parser.get_default_component_version('helm_chart_operator'))
")
        export K8S_HELM_CHART_OPERATOR
    else
        K8S_HELM_CHART=$(python -c "
from utils.k8s.k8s_components_parser import K8sComponentsParser
parser = K8sComponentsParser()
print(parser.get_default_component_version('helm_chart'))
")
        export K8S_HELM_CHART
    fi

    # Set default lib-init image for the selected language
    K8S_LIB_INIT_IMG=$(python -c "
from utils.k8s.k8s_components_parser import K8sComponentsParser
parser = K8sComponentsParser()
print(parser.get_default_component_version('lib_init', '$TEST_LIBRARY'))
")

    # Set default injector image (if cluster agent is used)
    if [[ "$SCENARIO" != *"NO_AC"* ]]; then
        K8S_INJECTOR_IMG=$(python -c "
from utils.k8s.k8s_components_parser import K8sComponentsParser
parser = K8sComponentsParser()
print(parser.get_default_component_version('injector'))
")
    else
        K8S_INJECTOR_IMG="''"
        CLUSTER_AGENT="''"
    fi

    echo "✅ Default component versions loaded."
}

review_and_customize_components() {
    spacer
    echo -e "${YELLOW}📋 Component Configuration Summary${NC}"
    echo ""
    echo "The following default component versions will be used:"
    echo ""
    echo "  🌐 Weblog:"
    echo "     - Image: ${WEBLOG_IMAGE}"
    echo ""
    echo "  📦 Lib-init ($TEST_LIBRARY):"
    echo "     - Image: ${K8S_LIB_INIT_IMG}"
    echo ""

    if [[ "$SCENARIO" != *"NO_AC"* ]]; then
        echo "  🔧 Cluster Agent:"
        echo "     - Image: ${CLUSTER_AGENT}"
        echo ""
        echo "  💉 Injector:"
        echo "     - Image: ${K8S_INJECTOR_IMG}"
        echo ""
    fi

    if [[ "$SCENARIO" == *"OPERATOR"* ]]; then
        echo "  ⚙️  Helm Chart Operator:"
        echo "     - Version: ${K8S_HELM_CHART_OPERATOR}"
        echo ""
    elif [[ "$SCENARIO" != *"NO_AC"* ]]; then
        echo "  📊 Helm Chart:"
        echo "     - Version: ${K8S_HELM_CHART}"
        echo ""
    fi

    echo ""
    read -p "Do you want to customize any component versions? (y/n): " CUSTOMIZE

    if [[ "$CUSTOMIZE" =~ ^[Yy]$ ]]; then
        while true; do
            echo ""
            echo -e "${CYAN}ℹ️  Select the component you want to customize (or 0 to finish):${NC}"
            echo "  1) Weblog image"
            echo "  2) Lib-init image"
            if [[ "$SCENARIO" != *"NO_AC"* ]]; then
                echo "  3) Cluster agent image"
                echo "  4) Injector image"
                if [[ "$SCENARIO" == *"OPERATOR"* ]]; then
                    echo "  5) Helm chart operator version"
                else
                    echo "  5) Helm chart version"
                fi
            fi
            echo "  0) Finish customization"
            echo ""

            read -p "Enter your choice: " CUSTOM_CHOICE

            case $CUSTOM_CHOICE in
                1)
                    select_weblog_img
                    ;;
                2)
                    select_lib_init_image_only
                    ;;
                3)
                    if [[ "$SCENARIO" != *"NO_AC"* ]]; then
                        select_cluster_agent
                    else
                        echo -e "${RED}❌ Invalid choice. Option 3 not available for NO_AC scenarios.${NC}"
                    fi
                    ;;
                4)
                    if [[ "$SCENARIO" != *"NO_AC"* ]]; then
                        select_injector_image_only
                    else
                        echo -e "${RED}❌ Invalid choice. Option 4 not available for NO_AC scenarios.${NC}"
                    fi
                    ;;
                5)
                    if [[ "$SCENARIO" != *"NO_AC"* ]]; then
                        select_helm_chart_version
                    else
                        echo -e "${RED}❌ Invalid choice. Option 5 not available for NO_AC scenarios.${NC}"
                    fi
                    ;;
                0)
                    break
                    ;;
                *)
                    echo -e "${RED}❌ Invalid choice. Please select a valid option.${NC}"
                    ;;
            esac
        done

        spacer
        echo -e "${GREEN}✅ Component customization complete!${NC}"
    else
        echo -e "${GREEN}✅ Using default component versions.${NC}"
    fi
}

# Helper function to select only lib-init image
select_lib_init_image_only() {
    spacer
    echo -e "${YELLOW}📌 Step: Configure Lib Init Image${NC}"
    echo "🔄 Fetching available lib-init images for $TEST_LIBRARY..."
    echo ""

    LIB_INIT_IMAGES=($(python -c "
from utils.k8s.k8s_components_parser import K8sComponentsParser
parser = K8sComponentsParser()
versions = parser.get_all_component_versions('lib_init', '$TEST_LIBRARY')
print(' '.join(versions))
"))

    if [[ ${#LIB_INIT_IMAGES[@]} -eq 0 ]]; then
        echo "❗No lib-init images found for $TEST_LIBRARY."
        read -p "Enter custom lib-init image: " K8S_LIB_INIT_IMG
    else
        echo "📝 Available lib-init images:"
        for i in "${!LIB_INIT_IMAGES[@]}"; do
            echo "$(($i + 1))) ${LIB_INIT_IMAGES[$i]}"
        done
        echo "$((${#LIB_INIT_IMAGES[@]} + 1))) Use custom image"

        while true; do
            read -p "Enter the number of the lib-init image you want to use: " lib_init_choice
            if [[ "$lib_init_choice" =~ ^[0-9]+$ ]] && (( lib_init_choice >= 1 && lib_init_choice <= ${#LIB_INIT_IMAGES[@]} + 1 )); then
                if (( lib_init_choice == ${#LIB_INIT_IMAGES[@]} + 1 )); then
                    read -p "Enter custom lib-init image: " K8S_LIB_INIT_IMG
                else
                    K8S_LIB_INIT_IMG="${LIB_INIT_IMAGES[$((lib_init_choice - 1))]}"
                fi
                break
            else
                echo "❌ Invalid choice. Please select a number between 1 and $((${#LIB_INIT_IMAGES[@]} + 1))."
            fi
        done
    fi
    echo "✅ Selected lib-init image: $K8S_LIB_INIT_IMG"
}

# Helper function to select only injector image
select_injector_image_only() {
    spacer
    echo -e "${YELLOW}📌 Step: Configure Injector Image${NC}"
    echo "🔄 Fetching available injector images..."
    echo ""

    INJECTOR_IMAGES=($(python -c "
from utils.k8s.k8s_components_parser import K8sComponentsParser
parser = K8sComponentsParser()
versions = parser.get_all_component_versions('injector')
print(' '.join(versions))
"))

    if [[ ${#INJECTOR_IMAGES[@]} -eq 0 ]]; then
        echo "❗No injector images found."
        read -p "Enter custom injector image: " K8S_INJECTOR_IMG
    else
        echo "📝 Available injector images:"
        for i in "${!INJECTOR_IMAGES[@]}"; do
            echo "$(($i + 1))) ${INJECTOR_IMAGES[$i]}"
        done
        echo "$((${#INJECTOR_IMAGES[@]} + 1))) Use custom image"

        while true; do
            read -p "Enter the number of the injector image you want to use: " injector_choice
            if [[ "$injector_choice" =~ ^[0-9]+$ ]] && (( injector_choice >= 1 && injector_choice <= ${#INJECTOR_IMAGES[@]} + 1 )); then
                if (( injector_choice == ${#INJECTOR_IMAGES[@]} + 1 )); then
                    read -p "Enter custom injector image: " K8S_INJECTOR_IMG
                else
                    K8S_INJECTOR_IMG="${INJECTOR_IMAGES[$((injector_choice - 1))]}"
                fi
                break
            else
                echo "❌ Invalid choice. Please select a number between 1 and $((${#INJECTOR_IMAGES[@]} + 1))."
            fi
        done
        echo "✅ Selected injector image: $K8S_INJECTOR_IMG"
    fi
}

run_the_tests(){
    spacer
    # 📌 Step: Confirm and execute
    echo ""
    echo "==============================================="
    echo "🚀 READY TO RUN THE TESTS! 🚀"
    echo "==============================================="
    echo ""
    echo "✨ Here's a summary of your selections:"
    echo "   🔹 Scenario:         $SCENARIO"
    echo "   🔹 Weblog:           $WEBLOG"
    echo "   🔹 Library init:     $K8S_LIB_INIT_IMG"
    echo "   🔹 Injector:         $K8S_INJECTOR_IMG"
    echo "   🔹 Cluster agent:    $CLUSTER_AGENT"
    if [[ -n "$K8S_HELM_CHART_OPERATOR" ]]; then
        echo "   🔹 Helm chart operator: $K8S_HELM_CHART_OPERATOR"
    else
        echo "   🔹 Helm chart:       ${K8S_HELM_CHART:-default}"
    fi
    echo "   🔹 Test Library:     $TEST_LIBRARY"
    echo ""

    # Ask if user wants to keep the cluster alive for debugging
    read -p "🔧 Do you want to keep the Kubernetes cluster alive after tests? (useful for debugging) (y/n): " KEEP_ALIVE

    echo -e "${CYAN}🚀 Ready to execute:${NC}"
    CMD=("./run.sh" "$SCENARIO" "--k8s-library" "$TEST_LIBRARY" "--k8s-weblog" "$WEBLOG" "--k8s-weblog-img" "$WEBLOG_IMAGE" "--k8s-cluster-img" "$CLUSTER_AGENT" "--k8s-lib-init-img" "$K8S_LIB_INIT_IMG" "--k8s-injector-img" "$K8S_INJECTOR_IMG" "--k8s-provider" "$K8S_PROVIDER")

    # Add --sleep parameter if user wants to keep cluster alive
    if [[ "$KEEP_ALIVE" == "y" ]]; then
        CMD+=("--sleep")
        echo -e "${YELLOW}⏳ Note: Cluster will remain alive after tests. You can inspect the environment.${NC}"
    fi

    echo -e "${GREEN}${CMD[*]}${NC}\n"
    read -p "⚠️  Do you want to execute the command? (y/n): " CONFIRM
    if [[ "$CONFIRM" == "y" ]]; then
        echo -e "${GREEN}▶️ Executing...${NC}"
        "${CMD[@]}"
    else
        echo -e "${RED}❌ Execution canceled.${NC}"
    fi
}
welcome "K8s lib-injection Tests"
load_requirements
ask_load_k8s_requirements
check_aws_account_access "$AWS_ECR_ACCOUNT"
configure_private_registry
ask_for_test_language
load_workflow_data "lib-injection,lib-injection-profiling" "libinjection_scenario_defs"
select_scenario
select_weblog
select_weblog_img
set_default_component_versions
review_and_customize_components
run_the_tests