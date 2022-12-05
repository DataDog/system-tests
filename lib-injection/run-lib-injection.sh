#!/bin/bash

# Fail on any command failure
set -e

# Absolute path to this script, e.g. /home/user/bin/foo.sh
SCRIPT_PATH=$(readlink -f "$0")
# Absolute path this script is in, thus /home/user/bin
export BASE_DIR=$(dirname "${SCRIPT_PATH}")

echo "Running library injection test cases"
echo "Deploying test agent"
${BASE_DIR}/run.sh $LIBRARY_INJECTION_CONNECTION $LIBRARY_INJECTION_ADMISSION_CONTROLLER deploy-agents
echo "Deploying pre-modified pod"
${BASE_DIR}/run.sh $LIBRARY_INJECTION_CONNECTION $LIBRARY_INJECTION_ADMISSION_CONTROLLER deploy-agents deploy-app
${BASE_DIR}/run.sh test-for-traces
kubectl logs pod/my-app
kubectl logs daemonset/datadog
