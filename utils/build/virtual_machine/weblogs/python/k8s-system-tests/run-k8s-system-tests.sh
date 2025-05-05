cd system-tests

#Create folder for app logs
sudo mkdir /var/log/datadog_weblog
sudo chmod 777 /var/log/datadog_weblog

TEST_LIBRARY="python"
K8S_WEBLOG="dd-lib-python-init-test-django"
K8S_WEBLOG_IMG="ghcr.io/datadog/system-tests/dd-lib-python-init-test-django:latest"
K8S_SCENARIO="K8S_LIB_INJECTION"
K8S_LIB_INIT_IMG="gcr.io/datadoghq/dd-lib-python-init:latest"
K8S_CLUSTER_IMG="gcr.io/datadoghq/cluster-agent:latest"
K8S_INJECTOR_IMG="gcr.io/datadoghq/apm-inject:latest"
echo "🚀 Loading system-tests requirements..."
./build.sh -i runner
# shellcheck source=/dev/null
source venv/bin/activate

    echo ""
    echo "==============================================="
    echo "🚀 READY TO RUN THE TESTS! 🚀"
    echo "==============================================="
    echo ""
    echo "✨ Here’s a summary of your selections:"
    echo "   🔹 Scenario:         $K8S_SCENARIO"
    echo "   🔹 Weblog:           $K8S_WEBLOG"
    echo "   🔹 Library init:     $K8S_LIB_INIT_IMG"
    echo "   🔹 Injector:         $K8S_INJECTOR_IMG"
    echo "   🔹 Cluster agent:    $K8S_CLUSTER_IMG"
    echo "   🔹 Test Library:     $TEST_LIBRARY"
    echo ""

./run.sh ${K8S_SCENARIO} --k8s-library ${TEST_LIBRARY} --k8s-weblog ${K8S_WEBLOG} --k8s-weblog-img ${K8S_WEBLOG_IMG} --k8s-lib-init-img ${K8S_LIB_INIT_IMG} --k8s-injector-img ${K8S_INJECTOR_IMG} --k8s-cluster-img ${K8S_CLUSTER_IMG} 
cp  logs_k8s_lib_injection/tests.log /var/log/datadog_weblog/app.log
cp  logs_k8s_lib_injection/*.log /var/log/datadog_weblog/