#!/bin/bash
# shellcheck disable=SC2207,SC2162,SC2206,SC1091,SC2076,SC2181,SC2004,SC2034

# Function: Add blank lines for better UX
spacer() {
    echo ""
    echo "-----------------------------------------------"
    echo ""
}

echo "========================================================="
echo "🚀 Welcome to System-Tests K8s Lib Inject Tests Wizard 🚀"
echo "========================================================="
echo ""

# 🎨 Colors for styling
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
CYAN='\033[1;36m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# 📌 Step: Ask user if they want to load system-tests requirements
read -p "⚙️  Do you want to load the system-tests requirements? This will execute: ./build.sh -i runner (y/n): " LOAD_REQ
if [[ "$LOAD_REQ" == "y" ]]; then
    ./build.sh -i runner
    source venv/bin/activate
    echo -e "${GREEN}✅ System-tests environment loaded.${NC}"
fi

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

# 📌 Step: Choose TEST_LIBRARY
echo -e "${YELLOW}📌 Step: Choose the language to test${NC}"
options=("java" "python" "nodejs" "ruby" "dotnet")
select TEST_LIBRARY in "${options[@]}"; do
    if [[ " ${options[*]} " =~ " ${TEST_LIBRARY} " ]]; then
        echo -e "${GREEN}✅ You selected: ${TEST_LIBRARY}${NC}"
        break
    else
        echo -e "${RED}❌ Invalid option. Please select a valid language.${NC}"
    fi
done

select_scenario() {
    spacer
    echo "🔄 Running Python script to compute workflow parameters..."

    # Run the Python script and capture the JSON output
    WORKFLOW_JSON=$(python utils/scripts/compute-workflow-parameters.py "$TEST_LIBRARY" -g "lib-injection" --parametric-job-count 1 --ci-environment "prod" --format json)
    export WORKFLOW_JSON=$(echo "$WORKFLOW_JSON" | jq '.libinjection_scenario_defs')

    if [[ $? -ne 0 ]]; then
        echo "❌ Error: Failed to execute the Python script."
        exit 1
    fi

    echo "✅ Successfully retrieved workflow parameters."
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
            SCENARIO="${SCENARIOS[$((scenario_choice - 1))]}"
            break
        else
            echo "❌ Invalid choice. Please select a number between 1 and ${#SCENARIOS[@]}."
        fi
    done

    echo "✅ Selected scenario: $SCENARIO"
}

# Call the function to select a scenario
select_scenario

# Select the weblog based on the chosen scenario
select_weblog() {
    spacer
    echo -e "${YELLOW}📌 Step: Select the weblog${NC}"
    echo "🔄 Fetching weblogs for the selected scenario: $SCENARIO..."

    # Extract available weblogs (second-level keys under the selected SCENARIO)
    WEBLOGS=($(echo "$WORKFLOW_JSON" | python -c "import sys, json; data=json.load(sys.stdin); print(' '.join(data.get('$SCENARIO', {}).keys()))"))

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
}
select_weblog_img(){
    spacer
    echo -e "${YELLOW}📌 Step: Select weblog img registry${NC}"
    WEBLOG_IMAGE="ghcr.io/datadog/system-tests/$WEBLOG:latest"
    select K8S_INJECTOR_IMG in "${WEBLOG_IMAGE[@]}" "Use custom image"; do
        if [[ -n "$WEBLOG_IMAGE" ]]; then
            break
        fi
    done
    if [[ "$WEBLOG_IMAGE" == "Use custom image" ]]; then
        read -p "Enter custom weblog image: " WEBLOG_IMAGE
    fi
}
# Call the function to select a weblog
select_weblog
select_weblog_img


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

# Call the function to select a cluster agent
select_cluster_agent

# 📌 Step: Extract cluster agents safely
spacer
echo -e "${YELLOW}📌 Step: Configure Lib Init Image${NC}"
LIB_INIT_IMAGES_java=("gcr.io/datadoghq/dd-lib-java-init:latest" "ghcr.io/datadog/dd-trace-java/dd-lib-java-init:latest_snapshot")
LIB_INIT_IMAGES_dotnet=("gcr.io/datadoghq/dd-lib-dotnet-init:latest" "ghcr.io/datadog/dd-trace-dotnet/dd-lib-dotnet-init:latest_snapshot")
LIB_INIT_IMAGES_nodejs=("gcr.io/datadoghq/dd-lib-js-init:latest" "ghcr.io/datadog/dd-trace-js/dd-lib-js-init:latest_snapshot")
LIB_INIT_IMAGES_python=("gcr.io/datadoghq/dd-lib-python-init:latest" "ghcr.io/datadog/dd-trace-py/dd-lib-python-init:latest_snapshot")
LIB_INIT_IMAGES_ruby=("gcr.io/datadoghq/dd-lib-ruby-init:latest" "ghcr.io/datadog/dd-trace-rb/dd-lib-ruby-init:latest_snapshot")

LIB_INIT_IMAGES_VAR="LIB_INIT_IMAGES_${TEST_LIBRARY}[@]"
DEFAULT_LIB_INIT_IMAGES=(${!LIB_INIT_IMAGES_VAR})

select K8S_LIB_INIT_IMG in "${DEFAULT_LIB_INIT_IMAGES[@]}" "Use custom image"; do
    if [[ -n "$K8S_LIB_INIT_IMG" ]]; then
        break
    fi
done
if [[ "$K8S_LIB_INIT_IMG" == "Use custom image" ]]; then
    read -p "Enter custom tracer lib init image: " K8S_LIB_INIT_IMG
fi

if [[ -z "$CLUSTER_AGENT" || "$CLUSTER_AGENT" == "null" ]]; then
    echo -e "${CYAN}ℹ️  No cluster agent found, skipping injector configuration.${NC}"
    K8S_INJECTOR_IMG="''"
    CLUSTER_AGENT="''"
else
    spacer
    echo -e "${YELLOW}📌 Step: Configure Injector Image${NC}"
    INJECTOR_IMAGES=("gcr.io/datadoghq/apm-inject:latest" "ghcr.io/datadog/apm-inject:latest_snapshot")
    select K8S_INJECTOR_IMG in "${INJECTOR_IMAGES[@]}" "Use custom image"; do
        if [[ -n "$K8S_INJECTOR_IMG" ]]; then
            break
        fi
    done
    if [[ "$K8S_INJECTOR_IMG" == "Use custom image" ]]; then
        read -p "Enter custom injector image: " K8S_INJECTOR_IMG
    fi
fi

# Final confirmation and execution

spacer
# 📌 Step: Confirm and execute
echo ""
echo "==============================================="
echo "🚀 READY TO RUN THE TESTS! 🚀"
echo "==============================================="
echo ""
echo "✨ Here’s a summary of your selections:"
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