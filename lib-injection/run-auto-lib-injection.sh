#!/bin/bash

# Fail on any command failure
set -e

# Absolute path to this script, e.g. /home/user/bin/foo.sh
SCRIPT_PATH=$(readlink -f "$0")
# Absolute path this script is in, thus /home/user/bin
export BASE_DIR=$(dirname "${SCRIPT_PATH}")


echo "**************************"
echo "*  Running Test Case #1  *"
echo "**************************"

echo "[run-auto-lib-injection TesCase#1] Deploying deployment"
${BASE_DIR}/execFunction.sh deploy-app-auto
echo "[run-auto-lib-injection TesCase#1] Deploying agents"
${BASE_DIR}/execFunction.sh deploy-agents-auto
echo "[run-auto-lib-injection TesCase#1] Trigger config"
${BASE_DIR}/execFunction.sh trigger-config-auto
echo "[run-auto-lib-injection TesCase#1] Running tests"
${BASE_DIR}/execFunction.sh test-for-traces-auto
${BASE_DIR}/execFunction.sh check-for-env-vars
echo "[run-auto-lib-injection TesCase#1] Cleaning up resources"
${BASE_DIR}/execFunction.sh cleanup-auto
echo "[run-auto-lib-injection TesCase#1] Completed successfully"

echo "**************************"
echo "*  Running Test Case #2  *"
echo "**************************"


echo "[run-auto-lib-injection TesCase#2] Deploying deployment"
${BASE_DIR}/execFunction.sh deploy-app-auto
echo "[run-auto-lib-injection TesCase#2] Deploying agents"
${BASE_DIR}/execFunction.sh deploy-agents-auto
echo "[run-auto-lib-injection TesCase#2] Trigger default config"
${BASE_DIR}/execFunction.sh trigger-config-auto
echo "[run-auto-lib-injection TesCase#2] Running tests for default config"
${BASE_DIR}/execFunction.sh test-for-traces-auto
echo "[run-auto-lib-injection TesCase#2] Trigger config-1"
CONFIG_NAME=config-1 ${BASE_DIR}/execFunction.sh trigger-config-auto
echo "[run-auto-lib-injection TesCase#1] Running tests for config-1"
${BASE_DIR}/execFunction.sh test-for-traces-auto
CONFIG_NAME=config-1 ${BASE_DIR}/execFunction.sh check-for-env-vars
echo "[run-auto-lib-injection TesCase#2] Completed successfully"
