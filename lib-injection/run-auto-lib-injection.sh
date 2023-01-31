#!/bin/bash

# Fail on any command failure
set -e

# Absolute path to this script, e.g. /home/user/bin/foo.sh
SCRIPT_PATH=$(readlink -f "$0")
# Absolute path this script is in, thus /home/user/bin
export BASE_DIR=$(dirname "${SCRIPT_PATH}")

if [ -z "${TEST_CASE}" ] ; then
    echo "MUST define TEST_CASE before sourcing this file"
    exit 1
fi

if [ $TEST_CASE == "TC1" ]; then
    # Nominal case:
    #   - deploy app & agent
    #   - apply config
    #   - check for traces

    echo "**************************"
    echo "*  Running Test Case #1  *"
    echo "**************************"

    echo "[run-auto-lib-injection] Deploying deployment"
    ${BASE_DIR}/execFunction.sh deploy-app-auto
    echo "[run-auto-lib-injection] Deploying agents"
    ${BASE_DIR}/execFunction.sh deploy-agents-auto
    echo "[run-auto-lib-injection] Trigger config"
    ${BASE_DIR}/execFunction.sh trigger-config-auto
    echo "[run-auto-lib-injection] Running tests"
    ${BASE_DIR}/execFunction.sh test-for-traces-auto
    ${BASE_DIR}/execFunction.sh check-for-env-vars
    echo "[run-auto-lib-injection] Completed successfully"
fi

if [ $TEST_CASE == "TC2" ]; then
    # Config change:
    #   - deploy app & agent
    #   - apply config
    #   - check for traces
    #   - apply different tracers config
    #   - check for traces

    echo "**************************"
    echo "*  Running Test Case #2  *"
    echo "**************************"

    echo "[run-auto-lib-injection] Deploying deployment"
    ${BASE_DIR}/execFunction.sh deploy-app-auto
    echo "[run-auto-lib-injection] Deploying agents"
    ${BASE_DIR}/execFunction.sh deploy-agents-auto
    echo "[run-auto-lib-injection] Trigger default config"
    ${BASE_DIR}/execFunction.sh trigger-config-auto
    echo "[run-auto-lib-injection] Running tests for default config"
    ${BASE_DIR}/execFunction.sh test-for-traces-auto
    echo "[run-auto-lib-injection] Trigger config-1"
    CONFIG_NAME=config-1 ${BASE_DIR}/execFunction.sh trigger-config-auto
    echo "[run-auto-lib-injection] Running tests for config-1"
    ${BASE_DIR}/execFunction.sh test-for-traces-auto
    CONFIG_NAME=config-1 ${BASE_DIR}/execFunction.sh check-for-env-vars
    echo "[run-auto-lib-injection] Completed successfully"
fi

if [ $TEST_CASE == "TC3" ]; then
    # Config persistence:
    #   - deploy app & agent
    #   - apply config
    #   - check for traces
    #   - trigger unrelated rolling-update
    #   - check for traces
    
    echo "**************************"
    echo "*  Running Test Case #3  *"
    echo "**************************"

    echo "[run-auto-lib-injection] Deploying deployment"
    ${BASE_DIR}/execFunction.sh deploy-app-auto
    echo "[run-auto-lib-injection] Deploying agents"
    ${BASE_DIR}/execFunction.sh deploy-agents-auto
    echo "[run-auto-lib-injection] Trigger config"
    ${BASE_DIR}/execFunction.sh trigger-config-auto
    echo "[run-auto-lib-injection] Running tests"
    ${BASE_DIR}/execFunction.sh test-for-traces-auto
    ${BASE_DIR}/execFunction.sh check-for-env-vars
    echo "[run-auto-lib-injection] Trigger unrelated rolling-update"
    ${BASE_DIR}/execFunction.sh trigger-app-rolling-update
    echo "[run-auto-lib-injection] Running tests"
    ${BASE_DIR}/execFunction.sh test-for-traces-auto
    ${BASE_DIR}/execFunction.sh check-for-env-vars
    echo "[run-auto-lib-injection] Completed successfully"
fi
