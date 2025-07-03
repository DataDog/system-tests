#!/bin/bash
# shellcheck disable=all
# This script is a wizard to help run k8s injector dev scenarios

source utils/scripts/ssi_wizards/common_wizard_functions.sh

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

ask_load_injector_dev_binary(){
    spacer
    echo -e "${YELLOW}📌 Step: Check Injector Dev Binary${NC}"
    
    # Check if injector-dev binary exists in binaries folder
    if [[ -f "binaries/injector-dev" ]]; then
        echo -e "${GREEN}✅ injector-dev binary found in binaries folder.${NC}"
        return
    fi
    
    echo -e "${YELLOW}⚠️  injector-dev binary not found in binaries folder.${NC}"
    echo "Please provide the source for the injector-dev binary:"
    echo "1) Local file path"
    echo "2) Download from URL"
    echo ""
    
    read -p "Enter your choice (1 or 2): " binary_choice
    
    case "$binary_choice" in
        1)
            read -p "Enter the local path to injector-dev binary: " LOCAL_BINARY_PATH
            if [[ -z "$LOCAL_BINARY_PATH" ]]; then
                echo -e "${RED}❌ Local path cannot be empty.${NC}"
                ask_load_injector_dev_binary
                return
            fi
            
            if [[ ! -f "$LOCAL_BINARY_PATH" ]]; then
                echo -e "${RED}❌ File not found: $LOCAL_BINARY_PATH${NC}"
                ask_load_injector_dev_binary
                return
            fi
            
            echo "Copying injector-dev binary to binaries folder..."
            cp "$LOCAL_BINARY_PATH" "binaries/injector-dev"
            if [[ $? -eq 0 ]]; then
                chmod +x "binaries/injector-dev"
                echo -e "${GREEN}✅ injector-dev binary copied successfully.${NC}"
            else
                echo -e "${RED}❌ Failed to copy injector-dev binary.${NC}"
                ask_load_injector_dev_binary
            fi
            ;;
        2)
            read -p "Enter the URL to download injector-dev binary: " BINARY_URL
            if [[ -z "$BINARY_URL" ]]; then
                echo -e "${RED}❌ URL cannot be empty.${NC}"
                ask_load_injector_dev_binary
                return
            fi
            
            echo "Downloading injector-dev binary from $BINARY_URL..."
            if command_exists curl; then
                curl -L -o "binaries/injector-dev" "$BINARY_URL"
            elif command_exists wget; then
                wget -O "binaries/injector-dev" "$BINARY_URL"
            else
                echo -e "${RED}❌ Neither curl nor wget is available for downloading.${NC}"
                ask_load_injector_dev_binary
                return
            fi
            
            if [[ $? -eq 0 ]]; then
                chmod +x "binaries/injector-dev"
                echo -e "${GREEN}✅ injector-dev binary downloaded successfully.${NC}"
            else
                echo -e "${RED}❌ Failed to download injector-dev binary.${NC}"
                ask_load_injector_dev_binary
            fi
            ;;
        *)
            echo -e "${RED}❌ Invalid choice. Please select 1 or 2.${NC}"
            ask_load_injector_dev_binary
            ;;
    esac
}

ask_load_k8s_injector_dev_requirements(){
    spacer
    echo -e "${YELLOW}📌 Step: Install K8s Injector Dev Requirements${NC}"
    echo "The following tools are required for K8s injector dev scenarios:"
    echo "  - Colima (for the default colima platform)"
    echo "  - MiniKube"
    echo "  - Helm"
    echo "  - Kubectl"
    echo ""
    
    read -p "Do you want to install the required software? (y/n): " INSTALL_TOOLS
    if [[ "$INSTALL_TOOLS" != "y" ]]; then
        echo -e "${CYAN}ℹ️  Skipping tool installation. Make sure you have all required tools installed.${NC}"
        return
    fi

    # Check and install Colima
    if ! command_exists colima; then
        read -p "⚠️  Colima is not installed. Do you want to install it? (y/n): " INSTALL_COLIMA
        if [[ "$INSTALL_COLIMA" == "y" ]]; then
            echo "Installing Colima..."
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                if command_exists brew; then
                    brew install colima
                else
                    echo -e "${RED}❌ Homebrew not found. Please install Homebrew first or install Colima manually.${NC}"
                fi
            elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                # Linux
                curl -LO https://github.com/abiosoft/colima/releases/latest/download/colima-linux-x86_64
                chmod +x colima-linux-x86_64
                sudo mv colima-linux-x86_64 /usr/local/bin/colima
            fi
            echo -e "${GREEN}✅ Colima installed successfully.${NC}"
        fi
    else
        echo -e "${GREEN}✅ Colima is already installed.${NC}"
    fi

    # Check and install MiniKube
    if ! command_exists minikube; then
        read -p "⚠️  MiniKube is not installed. Do you want to install it? (y/n): " INSTALL_MINIKUBE
        if [[ "$INSTALL_MINIKUBE" == "y" ]]; then
            echo "Installing MiniKube..."
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                ARCH=$(uname -m)
                if [[ "$ARCH" == "arm64" ]]; then
                    curl -LO https://github.com/kubernetes/minikube/releases/latest/download/minikube-darwin-arm64
                    sudo install minikube-darwin-arm64 /usr/local/bin/minikube
                    rm minikube-darwin-arm64
                else
                    curl -LO https://github.com/kubernetes/minikube/releases/latest/download/minikube-darwin-amd64
                    sudo install minikube-darwin-amd64 /usr/local/bin/minikube
                    rm minikube-darwin-amd64
                fi
            elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                # Linux
                curl -LO https://github.com/kubernetes/minikube/releases/latest/download/minikube-linux-amd64
                sudo install minikube-linux-amd64 /usr/local/bin/minikube
                rm minikube-linux-amd64
            fi
            echo -e "${GREEN}✅ MiniKube installed successfully.${NC}"
        fi
    else
        echo -e "${GREEN}✅ MiniKube is already installed.${NC}"
    fi

    # Check and install Helm
    if ! command_exists helm; then
        read -p "⚠️  Helm is not installed. Do you want to install it? (y/n): " INSTALL_HELM
        if [[ "$INSTALL_HELM" == "y" ]]; then
            echo "Installing Helm..."
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                if command_exists brew; then
                    brew install helm
                else
                    curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
                fi
            elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                # Linux
                curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
            fi
            echo -e "${GREEN}✅ Helm installed successfully.${NC}"
        fi
    else
        echo -e "${GREEN}✅ Helm is already installed.${NC}"
    fi

    # Check and install Kubectl
    if ! command_exists kubectl; then
        read -p "⚠️  Kubectl is not installed. Do you want to install it? (y/n): " INSTALL_KUBECTL
        if [[ "$INSTALL_KUBECTL" == "y" ]]; then
            echo "Installing Kubectl..."
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                if command_exists brew; then
                    brew install kubectl
                else
                    ARCH=$(uname -m)
                    if [[ "$ARCH" == "arm64" ]]; then
                        curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/darwin/arm64/kubectl"
                    else
                        curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/darwin/amd64/kubectl"
                    fi
                    chmod +x kubectl
                    sudo mv kubectl /usr/local/bin/
                fi
            elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                # Linux
                curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
                chmod +x kubectl
                sudo mv kubectl /usr/local/bin/
            fi
            echo -e "${GREEN}✅ Kubectl installed successfully.${NC}"
        fi
    else
        echo -e "${GREEN}✅ Kubectl is already installed.${NC}"
    fi

    echo -e "${GREEN}✅ All tools check completed.${NC}"
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

    echo "✅ Selected weblog image: $WEBLOG_IMAGE"
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

confirm_root_registry(){
    spacer
    echo -e "${YELLOW}📌 Step: Confirm Root Registry for Injection Images${NC}"
    echo "All injection images (cluster agent, apm-injector and lib-init) must be in the same registry path."
    echo ""
    echo "Default registry path: ${PRIVATE_DOCKER_REGISTRY}/ssi"
    echo "Example final format: ${PRIVATE_DOCKER_REGISTRY}/ssi/"
    echo ""
    
    read -p "Do you want to use the default registry path? (y/n): " USE_DEFAULT_REGISTRY
    
    if [[ "$USE_DEFAULT_REGISTRY" == "y" ]]; then
        K8S_SSI_REGISTRY_BASE="${PRIVATE_DOCKER_REGISTRY}/ssi"
    else
        read -p "Enter the registry path for injection images: " K8S_SSI_REGISTRY_BASE
    fi
    
    echo -e "${GREEN}✅ Registry path configured: $K8S_SSI_REGISTRY_BASE${NC}"
}

select_cluster_agent(){
    spacer
    echo -e "${YELLOW}📌 Step: Select Cluster Agent Image${NC}"
    echo "You only need to specify the image name and tag."
    echo "Examples: cluster-agent:latest, cluster-agent:v7.45.0"
    echo ""
    
    read -p "Enter cluster agent image name and tag: " CLUSTER_AGENT_IMAGE
    
    if [[ -z "$CLUSTER_AGENT_IMAGE" ]]; then
        echo -e "${RED}❌ Cluster agent image cannot be empty.${NC}"
        select_cluster_agent
        return
    fi
    
    echo -e "${GREEN}✅ Selected cluster agent: $CLUSTER_AGENT_IMAGE${NC}"
}

select_lib_init_and_injector(){
    spacer
    echo -e "${YELLOW}📌 Step: Select Lib Init and Injector Images${NC}"
    echo "You only need to specify the image names and tags."
    echo ""
    
    # Map language to correct lib-init image name
    local lib_init_default
    case "$TEST_LIBRARY" in
        "nodejs")
            lib_init_default="dd-lib-js-init:latest"
            ;;
        "java")
            lib_init_default="dd-lib-java-init:latest"
            ;;
        "dotnet")
            lib_init_default="dd-lib-dotnet-init:latest"
            ;;
        "python")
            lib_init_default="dd-lib-python-init:latest"
            ;;
        "ruby")
            lib_init_default="dd-lib-ruby-init:latest"
            ;;
        "php")
            lib_init_default="dd-lib-php-init:latest"
            ;;
        *)
            lib_init_default="dd-lib-init:latest"
            ;;
    esac
    
    echo "Default lib-init image for $TEST_LIBRARY: $lib_init_default"
    read -p "Enter lib-init image name and tag (or press Enter for default): " LIB_INIT_IMAGE
    
    if [[ -z "$LIB_INIT_IMAGE" ]]; then
        LIB_INIT_IMAGE="$lib_init_default"
    fi
    
    echo "Default injector image: apm-inject:latest"
    read -p "Enter injector image name and tag (or press Enter for default): " INJECTOR_IMAGE
    
    if [[ -z "$INJECTOR_IMAGE" ]]; then
        INJECTOR_IMAGE="apm-inject:latest"
    fi
    
    echo -e "${GREEN}✅ Selected lib-init image: $LIB_INIT_IMAGE${NC}"
    echo -e "${GREEN}✅ Selected injector image: $INJECTOR_IMAGE${NC}"
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
    echo "   🔹 Scenario:               $SCENARIO"
    echo "   🔹 Weblog:                 $WEBLOG"
    echo "   🔹 Weblog Image:           $WEBLOG_IMAGE"
    echo "   🔹 Test Library:           $TEST_LIBRARY"
    echo "   🔹 Cluster Agent:          $CLUSTER_AGENT_IMAGE"
    echo "   🔹 Lib Init:               $LIB_INIT_IMAGE"
    echo "   🔹 Injector:               $INJECTOR_IMAGE"
    echo "   🔹 SSI Registry Base:      $K8S_SSI_REGISTRY_BASE"
    echo ""

    echo -e "${CYAN}🚀 Ready to execute:${NC}"
    CMD=("./run.sh" "$SCENARIO" "--k8s-library" "$TEST_LIBRARY" "--k8s-weblog" "$WEBLOG" "--k8s-weblog-img" "$WEBLOG_IMAGE" "--k8s-cluster-img" "$CLUSTER_AGENT_IMAGE" "--k8s-lib-init-img" "$LIB_INIT_IMAGE" "--k8s-injector-img" "$INJECTOR_IMAGE" "--k8s-ssi-registry-base" "$K8S_SSI_REGISTRY_BASE")

    echo -e "${GREEN}${CMD[*]}${NC}\n"
    read -p "⚠️  Do you want to execute the command? (y/n): " CONFIRM
    if [[ "$CONFIRM" == "y" ]]; then
        echo -e "${GREEN}▶️ Executing...${NC}"
        "${CMD[@]}"
    else
        echo -e "${RED}❌ Execution canceled.${NC}"
    fi
}

# Main execution flow
welcome "K8s injector dev Tests"
ask_load_requirements
ask_load_injector_dev_binary
ask_load_k8s_injector_dev_requirements
configure_private_registry
ask_for_test_language
load_workflow_data "k8s_injector_dev" "k8s_injector_dev_scenario_defs"
select_scenario
select_weblog
select_weblog_img
migrate_images_to_private_registry
confirm_root_registry
select_cluster_agent
select_lib_init_and_injector
run_the_tests 