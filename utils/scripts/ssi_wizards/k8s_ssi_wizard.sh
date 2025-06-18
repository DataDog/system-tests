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
                curl -Lo ./kind https://kind.sigs.k8s.io/dl/$KIND_VERSION/kind-linux-amd64
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
}

configure_private_registry() {
    spacer
    echo -e "${YELLOW}📌 Step: Configure Private Registry${NC}"
    echo "You need to use a private registry to execute these tests."
    echo "Please select one of the following options:"
    echo "1) Use existing ECR registry (235494822917.dkr.ecr.us-east-1.amazonaws.com)"
    echo "2) Configure your own registry"
    
    read -p "Enter your choice (1 or 2): " registry_choice
    
    if [[ "$registry_choice" == "1" ]]; then
        echo "Configuring ECR registry..."
        export PRIVATE_DOCKER_REGISTRY="235494822917.dkr.ecr.us-east-1.amazonaws.com"
        export PRIVATE_DOCKER_REGISTRY_USER="AWS"
        
        # Login to ECR and get token
        aws-vault exec sso-apm-ecosystems-reliability-account-admin -- aws ecr get-login-password | docker login --username AWS --password-stdin 235494822917.dkr.ecr.us-east-1.amazonaws.com
        export PRIVATE_DOCKER_REGISTRY_TOKEN=$(aws-vault exec sso-apm-ecosystems-reliability-account-admin -- aws ecr get-login-password --region us-east-1)
        
        echo -e "${GREEN}✅ ECR registry configured successfully.${NC}"
    elif [[ "$registry_choice" == "2" ]]; then
        read -p "Enter your registry URL: " PRIVATE_DOCKER_REGISTRY
        read -p "Enter your registry username: " PRIVATE_DOCKER_REGISTRY_USER
        read -sp "Enter your registry token/password: " PRIVATE_DOCKER_REGISTRY_TOKEN
        echo
        export PRIVATE_DOCKER_REGISTRY
        export PRIVATE_DOCKER_REGISTRY_USER
        export PRIVATE_DOCKER_REGISTRY_TOKEN
        echo -e "${GREEN}✅ Custom registry configured successfully.${NC}"
    else
        echo -e "${RED}❌ Invalid choice. Please select 1 or 2.${NC}"
        configure_private_registry
    fi
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

    select K8S_INJECTOR_IMG in "${WEBLOG_IMAGE[@]}" "Use custom image"; do
        if [[ -n "$WEBLOG_IMAGE" ]]; then
            break
        fi
    done
    if [[ "$WEBLOG_IMAGE" == "Use custom image" ]]; then
        read -p "Enter custom weblog image: " WEBLOG_IMAGE
    fi
}

select_cluster_agent() {
    spacer
    echo -e "${YELLOW}📌 Step: Select the cluster agent${NC}"
    echo "🔄 Fetching available cluster agent images for:"
    echo "   - Test Library: $TEST_LIBRARY"
    echo "   - Scenario: $SCENARIO"
    echo "   - Weblog: $WEBLOG"
    echo ""

    # Extract available virtual machines (third-level keys under TEST_LIBRARY > SCENARIO > WEBLOG)
    CLUSTER_AGENTS=($(echo "$WORKFLOW_JSON" | python -c "
import sys, json
data = json.load(sys.stdin)
cluster_agents = data.get('$SCENARIO', {}).get('$WEBLOG', [])
print(' '.join(cluster_agents))
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

migrate_images_to_private_registry() {
    if [[ "$PRIVATE_DOCKER_REGISTRY" == "235494822917.dkr.ecr.us-east-1.amazonaws.com" ]]; then
        return
    fi

    spacer
    echo -e "${YELLOW}📌 Step: Migrate Public Images to Private Registry${NC}"
    read -p "Do you want to migrate public images to your private registry?[cluster-agent, injector, lib-init] (y/n): " MIGRATE_IMAGES
    
    if [[ "$MIGRATE_IMAGES" != "y" ]]; then
        return
    fi

    echo -e "${YELLOW}⚠️  Warning: Using 'latest' tag might impact CI as it uses latest by default.${NC}"
    
    # Function to pull and push an image
    pull_and_push_image() {
        local source_image=$1
        local target_name=$2
        local default_tag=$3
        
        echo "Processing $target_name..."
        read -p "Enter tag for $target_name (default: $default_tag): " custom_tag
        local tag=${custom_tag:-$default_tag}
        
        echo "Pulling $source_image..."
        docker pull "$source_image"
        if [[ $? -ne 0 ]]; then
            echo -e "${RED}❌ Failed to pull $source_image${NC}"
            return 1
        fi
        
        local target_image="${PRIVATE_DOCKER_REGISTRY}/ssi/${target_name}:${tag}"
        echo "Tagging and pushing to $target_image..."
        docker tag "$source_image" "$target_image"
        docker push "$target_image"
        
        if [[ $? -eq 0 ]]; then
            echo -e "${GREEN}✅ Successfully migrated $target_name${NC}"
            # Update the corresponding variable
            case "$target_name" in
                "dd-lib-js-init"|"dd-lib-java-init"|"dd-lib-dotnet-init"|"dd-lib-python-init"|"dd-lib-ruby-init"|"dd-lib-php-init")
                    K8S_LIB_INIT_IMG="$target_image"
                    ;;
                "apm-inject")
                    K8S_INJECTOR_IMG="$target_image"
                    ;;
                "cluster-agent")
                    CLUSTER_AGENT="$target_image"
                    ;;
            esac
        else
            echo -e "${RED}❌ Failed to push $target_image${NC}"
            return 1
        fi
    }

    # Map language to correct lib-init image name
    local lib_init_name
    case "$TEST_LIBRARY" in
        "nodejs")
            lib_init_name="dd-lib-js-init"
            ;;
        "java")
            lib_init_name="dd-lib-java-init"
            ;;
        "dotnet")
            lib_init_name="dd-lib-dotnet-init"
            ;;
        "python")
            lib_init_name="dd-lib-python-init"
            ;;
        "ruby")
            lib_init_name="dd-lib-ruby-init"
            ;;
        "php")
            lib_init_name="dd-lib-php-init"
            ;;
        *)
            echo -e "${RED}❌ Unsupported language: $TEST_LIBRARY${NC}"
            return 1
            ;;
    esac

    # Migrate lib-init image
    local lib_init_source="gcr.io/datadoghq/${lib_init_name}:latest"
    pull_and_push_image "$lib_init_source" "$lib_init_name" "latest"

    # Migrate apm-injector and cluster-agent
    pull_and_push_image "gcr.io/datadoghq/apm-inject:latest" "apm-inject" "latest"
    pull_and_push_image "gcr.io/datadoghq/cluster-agent:latest" "cluster-agent" "latest"

    echo -e "${GREEN}✅ Image migration completed${NC}"
}

select_lib_init_and_injector(){
    spacer
    echo -e "${YELLOW}📌 Step: Configure Lib Init Image${NC}"
    LIB_INIT_IMAGES_java=("235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-java-init:latest" "235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-java-init:latest_snapshot")
    LIB_INIT_IMAGES_dotnet=("235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-dotnet-init:latest" "235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-dotnet-init:latest_snapshot")
    LIB_INIT_IMAGES_nodejs=("235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-js-init:latest" "235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-js-init:latest_snapshot")
    LIB_INIT_IMAGES_python=("235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-python-init:latest" "235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-python-init:latest_snapshot")
    LIB_INIT_IMAGES_ruby=("235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-ruby-init:latest" "235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-ruby-init:latest_snapshot")
    LIB_INIT_IMAGES_php=("235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-php-init:latest" "235494822917.dkr.ecr.us-east-1.amazonaws.com/ssi/dd-lib-php-init:latest_snapshot")

    LIB_INIT_IMAGES_VAR="LIB_INIT_IMAGES_${TEST_LIBRARY}[@]"
    DEFAULT_LIB_INIT_IMAGES=(${!LIB_INIT_IMAGES_VAR})

    # Add migrated lib-init image if it exists
    if [[ -n "$K8S_LIB_INIT_IMG" && "$K8S_LIB_INIT_IMG" != "null" ]]; then
        DEFAULT_LIB_INIT_IMAGES+=("$K8S_LIB_INIT_IMG")
    fi

    echo "📝 Available lib-init images:"
    for i in "${!DEFAULT_LIB_INIT_IMAGES[@]}"; do
        echo "$(($i + 1))) ${DEFAULT_LIB_INIT_IMAGES[$i]}"
    done
    echo "$((${#DEFAULT_LIB_INIT_IMAGES[@]} + 1))) Use custom image"

    while true; do
        read -p "Enter the number of the lib-init image you want to use: " lib_init_choice
        if [[ "$lib_init_choice" =~ ^[0-9]+$ ]] && (( lib_init_choice >= 1 && lib_init_choice <= ${#DEFAULT_LIB_INIT_IMAGES[@]} + 1 )); then
            if (( lib_init_choice == ${#DEFAULT_LIB_INIT_IMAGES[@]} + 1 )); then
                read -p "Enter custom lib-init image: " K8S_LIB_INIT_IMG
            else
                K8S_LIB_INIT_IMG="${DEFAULT_LIB_INIT_IMAGES[$((lib_init_choice - 1))]}"
            fi
            break
        else
            echo "❌ Invalid choice. Please select a number between 1 and $((${#DEFAULT_LIB_INIT_IMAGES[@]} + 1))."
        fi
    done
    echo "✅ Selected lib-init image: $K8S_LIB_INIT_IMG"

    if [[ -z "$CLUSTER_AGENT" || "$CLUSTER_AGENT" == "null" ]]; then
        echo -e "${CYAN}ℹ️  No cluster agent found, skipping injector configuration.${NC}"
        K8S_INJECTOR_IMG="''"
        CLUSTER_AGENT="''"
    else
        spacer
        echo -e "${YELLOW}📌 Step: Configure Injector Image${NC}"
        INJECTOR_IMAGES=("gcr.io/datadoghq/apm-inject:latest" "ghcr.io/datadog/apm-inject:latest_snapshot")

        # Add migrated injector image if it exists
        if [[ -n "$K8S_INJECTOR_IMG" && "$K8S_INJECTOR_IMG" != "null" ]]; then
            INJECTOR_IMAGES+=("$K8S_INJECTOR_IMG")
        fi

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
migrate_images_to_private_registry
select_cluster_agent
select_lib_init_and_injector
run_the_tests