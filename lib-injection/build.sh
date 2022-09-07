#!/bin/bash

# Absolute path to this script, e.g. /home/user/bin/foo.sh
SCRIPT_PATH=$(readlink -f "$0")
# Absolute path this script is in, thus /home/user/bin
SCRIPT_DIR=$(dirname "${SCRIPT_PATH}")

echo "Building not required for lib injection tests"
echo "Installing kind..."
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.14.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
echo "kind install complete"

echo "Installing kubectl..."
curl -LO https://dl.k8s.io/release/v1.24.0/bin/linux/amd64/kubectl
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
echo "kubectl install complete"

echo "Creating kube cluster"
./lib-injection/run.sh ensure-cluster

echo "Installing helm"
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh
