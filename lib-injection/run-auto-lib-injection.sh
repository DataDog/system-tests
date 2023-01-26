#!/bin/bash

# Fail on any command failure
set -e

# Absolute path to this script, e.g. /home/user/bin/foo.sh
SCRIPT_PATH=$(readlink -f "$0")
# Absolute path this script is in, thus /home/user/bin
export BASE_DIR=$(dirname "${SCRIPT_PATH}")

echo "[run-lib-injection] Deploying deployment"
${BASE_DIR}/execFunction.sh deploy-app-auto
echo "[run-lib-injection] Deploying agents"
${BASE_DIR}/execFunction.sh deploy-agents-auto
echo "[run-lib-injection] Trigger config"
${BASE_DIR}/execFunction.sh trigger-config-auto
echo "[run-lib-injection] Running tests"
${BASE_DIR}/execFunction.sh test-for-traces-auto

echo "[run-lib-injection] Completed successfully"
