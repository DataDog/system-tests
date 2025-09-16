#!/bin/bash

# Troubleshooting script for Kind cluster issues
# Run this when connected to the CI pod or locally

set -e
set +x  # Don't echo commands to avoid noise

echo "==============================================="
echo "Kind Cluster Troubleshooting Script"
echo "==============================================="

# Create output directory
mkdir -p troubleshoot-output
LOG_DIR="troubleshoot-output"

echo ""
echo "=== 1. Checking Kind Cluster Existence ==="
echo "kind get clusters" | tee "$LOG_DIR/commands.log"
kind get clusters 2>&1 | tee "$LOG_DIR/kind-clusters.log" || echo "Failed to get kind clusters" | tee -a "$LOG_DIR/kind-clusters.log"

echo ""
echo "=== 2. Kind Cluster Nodes ==="
echo "kind get nodes --name lib-injection-testing" | tee -a "$LOG_DIR/commands.log"
kind get nodes --name lib-injection-testing 2>&1 | tee "$LOG_DIR/kind-nodes.log" || echo "Failed to get kind nodes" | tee -a "$LOG_DIR/kind-nodes.log"

echo ""
echo "=== 3. Kind Generated Kubeconfig ==="
echo "kind get kubeconfig --name lib-injection-testing" | tee -a "$LOG_DIR/commands.log"
kind get kubeconfig --name lib-injection-testing 2>&1 | tee "$LOG_DIR/kind-kubeconfig.log" || echo "Failed to get kind kubeconfig" | tee -a "$LOG_DIR/kind-kubeconfig.log"

echo ""
echo "=== 4. Current Kubectl Configuration ==="
echo "kubectl config current-context" | tee -a "$LOG_DIR/commands.log"
kubectl config current-context 2>&1 | tee "$LOG_DIR/kubectl-context.log" || echo "Failed to get current context" | tee -a "$LOG_DIR/kubectl-context.log"

echo ""
echo "kubectl config get-contexts" | tee -a "$LOG_DIR/commands.log"
kubectl config get-contexts 2>&1 | tee -a "$LOG_DIR/kubectl-context.log" || echo "Failed to get contexts" | tee -a "$LOG_DIR/kubectl-context.log"

echo ""
echo "cat ~/.kube/config" | tee -a "$LOG_DIR/commands.log"
cat ~/.kube/config 2>&1 | tee "$LOG_DIR/active-kubeconfig.log" || echo "Failed to read kubeconfig" | tee -a "$LOG_DIR/active-kubeconfig.log"

echo ""
echo "=== 5. Cluster Connectivity Tests ==="
echo "kubectl cluster-info" | tee -a "$LOG_DIR/commands.log"
kubectl cluster-info 2>&1 | tee "$LOG_DIR/cluster-connectivity.log" || echo "Failed to get cluster info" | tee -a "$LOG_DIR/cluster-connectivity.log"

echo ""
echo "kubectl cluster-info --context kind-lib-injection-testing" | tee -a "$LOG_DIR/commands.log"
kubectl cluster-info --context kind-lib-injection-testing 2>&1 | tee -a "$LOG_DIR/cluster-connectivity.log" || echo "Failed to get kind cluster info" | tee -a "$LOG_DIR/cluster-connectivity.log"

echo ""
echo "=== 6. Kubernetes Cluster State ==="
echo "kubectl get nodes --show-labels" | tee -a "$LOG_DIR/commands.log"
kubectl get nodes --show-labels 2>&1 | tee "$LOG_DIR/k8s-nodes.log" || echo "Failed to get nodes" | tee -a "$LOG_DIR/k8s-nodes.log"

echo ""
echo "kubectl get namespaces" | tee -a "$LOG_DIR/commands.log"
kubectl get namespaces 2>&1 | tee "$LOG_DIR/k8s-namespaces.log" || echo "Failed to get namespaces" | tee -a "$LOG_DIR/k8s-namespaces.log"

echo ""
echo "kubectl get pods --all-namespaces" | tee -a "$LOG_DIR/commands.log"
kubectl get pods --all-namespaces 2>&1 | tee "$LOG_DIR/k8s-pods.log" || echo "Failed to get pods" | tee -a "$LOG_DIR/k8s-pods.log"

echo ""
echo "kubectl describe nodes" | tee -a "$LOG_DIR/commands.log"
kubectl describe nodes 2>&1 | tee "$LOG_DIR/k8s-nodes-describe.log" || echo "Failed to describe nodes" | tee -a "$LOG_DIR/k8s-nodes-describe.log"

echo ""
echo "=== 7. Docker Container Status ==="
echo "docker ps --filter name=lib-injection-testing" | tee -a "$LOG_DIR/commands.log"
docker ps --filter name=lib-injection-testing 2>&1 | tee "$LOG_DIR/docker-containers.log" || echo "Failed to list docker containers" | tee -a "$LOG_DIR/docker-containers.log"

echo ""
echo "docker inspect lib-injection-testing-control-plane" | tee -a "$LOG_DIR/commands.log"
docker inspect lib-injection-testing-control-plane 2>&1 | tee "$LOG_DIR/docker-inspect.log" || echo "Failed to inspect docker container" | tee -a "$LOG_DIR/docker-inspect.log"

echo ""
echo "docker logs lib-injection-testing-control-plane (last 100 lines)" | tee -a "$LOG_DIR/commands.log"
docker logs --tail 100 lib-injection-testing-control-plane 2>&1 | tee "$LOG_DIR/docker-logs.log" || echo "Failed to get docker logs" | tee -a "$LOG_DIR/docker-logs.log"

echo ""
echo "=== 8. Network Connectivity ==="
echo "ping -c 3 docker" | tee -a "$LOG_DIR/commands.log"
ping -c 3 docker 2>&1 | tee "$LOG_DIR/network-connectivity.log" || echo "Docker hostname not reachable" | tee -a "$LOG_DIR/network-connectivity.log"

echo ""
echo "ping -c 3 localhost" | tee -a "$LOG_DIR/commands.log"
ping -c 3 localhost 2>&1 | tee -a "$LOG_DIR/network-connectivity.log" || echo "Localhost not reachable" | tee -a "$LOG_DIR/network-connectivity.log"

echo ""
echo "netstat -tlnp | grep -E ':(6443|8127|18081)'" | tee -a "$LOG_DIR/commands.log"
netstat -tlnp 2>&1 | grep -E ":(6443|8127|18081)" | tee "$LOG_DIR/network-ports.log" || echo "No relevant ports listening" | tee "$LOG_DIR/network-ports.log"

echo ""
echo "=== 9. DNS Resolution ==="
echo "nslookup docker" | tee -a "$LOG_DIR/commands.log"
nslookup docker 2>&1 | tee "$LOG_DIR/dns-resolution.log" || echo "Failed to resolve docker" | tee -a "$LOG_DIR/dns-resolution.log"

echo ""
echo "nslookup localhost" | tee -a "$LOG_DIR/commands.log"
nslookup localhost 2>&1 | tee -a "$LOG_DIR/dns-resolution.log" || echo "Failed to resolve localhost" | tee -a "$LOG_DIR/dns-resolution.log"

echo ""
echo "=== 10. Docker Network Details ==="
echo "docker network ls" | tee -a "$LOG_DIR/commands.log"
docker network ls 2>&1 | tee "$LOG_DIR/docker-networks.log" || echo "Failed to list docker networks" | tee -a "$LOG_DIR/docker-networks.log"

echo ""
echo "docker network inspect kind" | tee -a "$LOG_DIR/commands.log"
docker network inspect kind 2>&1 | tee "$LOG_DIR/docker-network-kind.log" || echo "Failed to inspect kind network" | tee -a "$LOG_DIR/docker-network-kind.log"

echo ""
echo "=== 11. Commands Inside Kind Container ==="
echo "docker exec lib-injection-testing-control-plane kubectl get nodes" | tee -a "$LOG_DIR/commands.log"
docker exec lib-injection-testing-control-plane kubectl get nodes 2>&1 | tee "$LOG_DIR/inside-kind-nodes.log" || echo "Failed to exec kubectl in kind" | tee -a "$LOG_DIR/inside-kind-nodes.log"

echo ""
echo "docker exec lib-injection-testing-control-plane kubectl get pods -A" | tee -a "$LOG_DIR/commands.log"
docker exec lib-injection-testing-control-plane kubectl get pods -A 2>&1 | tee "$LOG_DIR/inside-kind-pods.log" || echo "Failed to get pods inside kind" | tee -a "$LOG_DIR/inside-kind-pods.log"

echo ""
echo "docker exec lib-injection-testing-control-plane netstat -tlnp | grep 6443" | tee -a "$LOG_DIR/commands.log"
docker exec lib-injection-testing-control-plane netstat -tlnp 2>&1 | grep 6443 | tee "$LOG_DIR/inside-kind-api-server.log" || echo "API server not listening inside kind" | tee "$LOG_DIR/inside-kind-api-server.log"

echo ""
echo "docker exec lib-injection-testing-control-plane ip addr show" | tee -a "$LOG_DIR/commands.log"
docker exec lib-injection-testing-control-plane ip addr show 2>&1 | tee "$LOG_DIR/inside-kind-network.log" || echo "Failed to get network info inside kind" | tee -a "$LOG_DIR/inside-kind-network.log"

echo ""
echo "=== 12. DaemonSet Debug (if applicable) ==="
echo "kubectl get daemonsets -n default" | tee -a "$LOG_DIR/commands.log"
kubectl get daemonsets -n default 2>&1 | tee "$LOG_DIR/daemonsets.log" || echo "Failed to get daemonsets" | tee -a "$LOG_DIR/daemonsets.log"

echo ""
echo "kubectl describe daemonset datadog -n default" | tee -a "$LOG_DIR/commands.log"
kubectl describe daemonset datadog -n default 2>&1 | tee "$LOG_DIR/daemonset-datadog.log" || echo "Datadog daemonset not found" | tee -a "$LOG_DIR/daemonset-datadog.log"

echo ""
echo "kubectl get events -n default --sort-by='.lastTimestamp'" | tee -a "$LOG_DIR/commands.log"
kubectl get events -n default --sort-by=".lastTimestamp" 2>&1 | tail -20 | tee "$LOG_DIR/k8s-events.log" || echo "Failed to get events" | tee -a "$LOG_DIR/k8s-events.log"

echo ""
echo "=== 13. Environment Variables ==="
echo "env | grep -E '(CI|DOCKER|GITLAB|KIND)'" | tee -a "$LOG_DIR/commands.log"
env | grep -E "(CI|DOCKER|GITLAB|KIND)" 2>&1 | tee "$LOG_DIR/environment.log" || echo "No relevant env vars found" | tee "$LOG_DIR/environment.log"

echo ""
echo "=== 14. Kind Config Files ==="
echo "find . -name '*kind-config*.yaml'" | tee -a "$LOG_DIR/commands.log"
find . -name "*kind-config*.yaml" 2>&1 | tee "$LOG_DIR/kind-config-files.log" || echo "No kind config files found" | tee -a "$LOG_DIR/kind-config-files.log"

# Show kind config content if found
for config_file in $(find . -name "*kind-config*.yaml" 2>/dev/null); do
    echo ""
    echo "=== Content of $config_file ===" | tee -a "$LOG_DIR/commands.log"
    echo "cat $config_file" | tee -a "$LOG_DIR/commands.log"
    cat "$config_file" 2>&1 | tee "$LOG_DIR/kind-config-content.log" || echo "Failed to read $config_file" | tee -a "$LOG_DIR/kind-config-content.log"
done

echo ""
echo "==============================================="
echo "Troubleshooting Complete!"
echo "==============================================="
echo "All output saved to: $LOG_DIR/"
echo ""
echo "Key files to check:"
echo "- $LOG_DIR/cluster-connectivity.log - API server connectivity"
echo "- $LOG_DIR/docker-logs.log - Kind container logs"
echo "- $LOG_DIR/k8s-nodes.log - Kubernetes nodes status"
echo "- $LOG_DIR/network-connectivity.log - Network connectivity tests"
echo "- $LOG_DIR/active-kubeconfig.log - Current kubeconfig"
echo "- $LOG_DIR/kind-kubeconfig.log - Kind-generated kubeconfig"
echo ""

# Summary
echo "=== QUICK SUMMARY ==="
echo "Kind clusters: $(kind get clusters 2>/dev/null | wc -l || echo 0)"
echo "Docker containers: $(docker ps --filter name=lib-injection-testing --format '{{.Names}}' 2>/dev/null || echo 'none')"
echo "Kubectl context: $(kubectl config current-context 2>/dev/null || echo 'none')"
echo "Cluster connectivity: $(kubectl cluster-info --request-timeout=5s >/dev/null 2>&1 && echo 'OK' || echo 'FAILED')"
echo "Nodes ready: $(kubectl get nodes --no-headers 2>/dev/null | grep -c Ready || echo 0)"
echo ""