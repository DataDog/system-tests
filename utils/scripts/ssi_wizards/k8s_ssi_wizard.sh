#!/bin/bash
# shellcheck disable=all
#This script was generated using chatgpt

source utils/scripts/ssi_wizards/common_wizard_functions.sh


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
    aws-vault exec sso-apm-ecosystems-reliability-account-admin -- aws ecr get-login-password | docker login --username AWS --password-stdin 235494822917.dkr.ecr.us-east-1.amazonaws.com
    export PRIVATE_DOCKER_REGISTRY_TOKEN=$(aws-vault exec sso-apm-ecosystems-reliability-account-admin -- aws ecr get-login-password --region us-east-1)

    echo -e "${GREEN}✅ ECR registry configured successfully.${NC}"
}

select_weblog_img(){
    spacer
    echo -e "${YELLOW}📌 Step: Select weblog img registry${NC}"
    WEBLOG_IMAGE="$PRIVATE_DOCKER_REGISTRY/system-tests/$WEBLOG:latest"

    # Ask if user wants to build and push the weblog
    read -p "Do you want to build and push the weblog? (y/n): " BUILD_WEBLOG
    if [[ "$BUILD_WEBLOG" == "y" ]]; then
        echo -e "${YELLOW}⚠️  Warning: Using 'latest' tag might impact CI as it uses latest by default.${NC}"
        read -p "Enter tag name for the weblog (e.g., v1.0.0): " TAG_NAME

        if [[ -z "$TAG_NAME" ]]; then
            echo -e "${RED}❌ Tag name cannot be empty.${NC}"
            select_weblog_img
            return
        fi

        echo "Building and pushing weblog..."
        ./lib-injection/build/build_lib_injection_weblog.sh -w "${WEBLOG}" -l "${TEST_LIBRARY}" \
            --push-tag "${PRIVATE_DOCKER_REGISTRY}/system-tests/${WEBLOG}:${TAG_NAME}" \
            --docker-platform linux/arm64,linux/amd64

        if [[ $? -eq 0 ]]; then
            echo -e "${GREEN}✅ Weblog built and pushed successfully.${NC}"
            WEBLOG_IMAGE="${PRIVATE_DOCKER_REGISTRY}/system-tests/${WEBLOG}:${TAG_NAME}"
        else
            echo -e "${RED}❌ Failed to build and push weblog.${NC}"
            read -p "Do you want to continue with existing image? (y/n): " CONTINUE
            if [[ "$CONTINUE" != "y" ]]; then
                echo -e "${RED}❌ Exiting...${NC}"
                exit 1
            fi
        fi
    fi

    select option in "${WEBLOG_IMAGE}" "Use custom image"; do
        if [[ -n "$option" ]]; then
            if [[ "$option" == "Use custom image" ]]; then
                read -p "Enter custom weblog image: " WEBLOG_IMAGE
            else
                WEBLOG_IMAGE="$option"
            fi
            break
        fi
    done
}

select_cluster_agent() {
    spacer
    echo -e "${YELLOW}📌 Step: Select the cluster agent${NC}"
    echo "🔄 Fetching available cluster agent images for:"
    echo "   - Test Library: $TEST_LIBRARY"
    echo "   - Scenario: $SCENARIO"
    echo "   - Weblog: $WEBLOG"
    echo ""

    # Extract cluster_agents from the new components structure
    # The new format is: {scenario: {weblog: [{cluster_agents: [{key: value}]}]}}
    CLUSTER_AGENTS=($(echo "$WORKFLOW_JSON" | python -c "
import sys, json
data = json.load(sys.stdin)
components = data.get('$SCENARIO', {}).get('$WEBLOG', [])
# Find the cluster_agents component
for comp in components:
    if 'cluster_agents' in comp:
        agents = comp['cluster_agents']
        # Extract all image values from the list of dicts
        images = [list(agent.values())[0] for agent in agents]
        print(' '.join(images))
        break
"))

    if [[ ${#CLUSTER_AGENTS[@]} -eq 0 ]]; then
        echo "❗No cluster agents supported for:"
        echo "   - Test Library: $TEST_LIBRARY"
        echo "   - Scenario: $SCENARIO"
        echo "   - Weblog: $WEBLOG"
    else
        # Add migrated cluster agent if it exists
        if [[ -n "$CLUSTER_AGENT" && "$CLUSTER_AGENT" != "null" ]]; then
            CLUSTER_AGENTS+=("$CLUSTER_AGENT")
        fi

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
    echo "🔄 Fetching available helm chart versions for:"
    echo "   - Scenario: $SCENARIO"
    echo "   - Weblog: $WEBLOG"
    echo ""

    # Try to extract helm_chart_operators first (for OPERATOR scenarios)
    HELM_CHART_OPERATOR_VERSIONS=($(echo "$WORKFLOW_JSON" | python -c "
import sys, json
data = json.load(sys.stdin)
components = data.get('$SCENARIO', {}).get('$WEBLOG', [])
for comp in components:
    if 'helm_chart_operators' in comp:
        helm_charts = comp['helm_chart_operators']
        versions = [list(chart.values())[0] for chart in helm_charts]
        print(' '.join(versions))
        break
"))

    # Try to extract regular helm_charts (for non-OPERATOR scenarios)
    HELM_CHART_VERSIONS=($(echo "$WORKFLOW_JSON" | python -c "
import sys, json
data = json.load(sys.stdin)
components = data.get('$SCENARIO', {}).get('$WEBLOG', [])
for comp in components:
    if 'helm_charts' in comp:
        helm_charts = comp['helm_charts']
        versions = [list(chart.values())[0] for chart in helm_charts]
        print(' '.join(versions))
        break
"))

    # Handle helm_chart_operators if found
    if [[ ${#HELM_CHART_OPERATOR_VERSIONS[@]} -gt 0 ]]; then
        if [[ ${#HELM_CHART_OPERATOR_VERSIONS[@]} -eq 1 ]]; then
            export K8S_HELM_CHART_OPERATOR="${HELM_CHART_OPERATOR_VERSIONS[0]}"
            echo "✅ Using Helm Chart Operator version: $K8S_HELM_CHART_OPERATOR"
        else
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
        fi
        return
    fi

    # Handle regular helm_charts if found
    if [[ ${#HELM_CHART_VERSIONS[@]} -gt 0 ]]; then
        if [[ ${#HELM_CHART_VERSIONS[@]} -eq 1 ]]; then
            export K8S_HELM_CHART="${HELM_CHART_VERSIONS[0]}"
            echo "✅ Using Helm Chart version: $K8S_HELM_CHART"
        else
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
        fi
        return
    fi

    # No helm charts found
    echo -e "${CYAN}ℹ️  No helm chart versions defined, using default.${NC}"
}

select_lib_init_and_injector(){
    spacer
    echo -e "${YELLOW}📌 Step: Configure Lib Init Image${NC}"
    echo "🔄 Fetching available lib-init images for:"
    echo "   - Test Library: $TEST_LIBRARY"
    echo "   - Scenario: $SCENARIO"
    echo "   - Weblog: $WEBLOG"
    echo ""

    # Extract lib_inits from the components structure
    LIB_INIT_IMAGES=($(echo "$WORKFLOW_JSON" | python -c "
import sys, json
data = json.load(sys.stdin)
components = data.get('$SCENARIO', {}).get('$WEBLOG', [])
# Find the lib_inits component
for comp in components:
    if 'lib_inits' in comp:
        lib_inits = comp['lib_inits']
        # Extract all image values from the list of dicts
        images = [list(lib_init.values())[0] for lib_init in lib_inits]
        print(' '.join(images))
        break
"))

    if [[ ${#LIB_INIT_IMAGES[@]} -eq 0 ]]; then
        echo "❗No lib-init images found for:"
        echo "   - Test Library: $TEST_LIBRARY"
        echo "   - Scenario: $SCENARIO"
        echo "   - Weblog: $WEBLOG"
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
        echo "🔄 Fetching available injector images for:"
        echo "   - Scenario: $SCENARIO"
        echo "   - Weblog: $WEBLOG"
        echo ""

        # Extract injectors from the components structure
        INJECTOR_IMAGES=($(echo "$WORKFLOW_JSON" | python -c "
import sys, json
data = json.load(sys.stdin)
components = data.get('$SCENARIO', {}).get('$WEBLOG', [])
# Find the injectors component
for comp in components:
    if 'injectors' in comp:
        injectors = comp['injectors']
        # Extract all image values from the list of dicts
        images = [list(injector.values())[0] for injector in injectors]
        print(' '.join(images))
        break
"))

        if [[ ${#INJECTOR_IMAGES[@]} -eq 0 ]]; then
            echo "❗No injector images found for scenario: $SCENARIO"
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

    echo -e "${CYAN}🚀 Ready to execute:${NC}"
    CMD=("./run.sh" "$SCENARIO" "--k8s-library" "$TEST_LIBRARY" "--k8s-weblog" "$WEBLOG" "--k8s-weblog-img" "$WEBLOG_IMAGE" "--k8s-cluster-img" "$CLUSTER_AGENT" "--k8s-lib-init-img" "$K8S_LIB_INIT_IMG" "--k8s-injector-img" "$K8S_INJECTOR_IMG" "--k8s-provider" "$K8S_PROVIDER")

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
ask_load_requirements
ask_load_k8s_requirements
configure_private_registry
ask_for_test_language
load_workflow_data "lib-injection,lib-injection-profiling" "libinjection_scenario_defs"
select_scenario
select_weblog
select_weblog_img
select_cluster_agent
select_helm_chart_version
select_lib_init_and_injector
run_the_tests