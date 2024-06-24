#!/bin/bash

# Fail on any command failure
set -e

# Absolute path to this script, e.g. /home/user/bin/foo.sh
SCRIPT_PATH=$(readlink -f "$0")
# Absolute path this script is in, thus /home/user/bin
export BASE_DIR=$(dirname "${SCRIPT_PATH}")

if [ -z "${TEST_CASE}" ]; then
    echo "MUST define TEST_CASE before sourcing this file"
    exit 1
fi

echo "**************************"
echo "*  Running Test Case ${TEST_CASE} *"
echo "**************************"

if [ $TEST_CASE == "TestCase1" ]; then
    # Nominal case:
    #   - deploy app & agent
    #   - apply config
    #   - check for traces
    echo "[run-auto-lib-injection] Deploying deployment"
    ${BASE_DIR}/execFunction.sh deploy-app-auto
    echo "[run-auto-lib-injection] Deploying agents"
    ${BASE_DIR}/execFunction.sh deploy-agents-auto
    echo "[run-auto-lib-injection] Apply config"
    ${BASE_DIR}/execFunction.sh apply-config-auto
    echo "[run-auto-lib-injection] Running tests"
    ${BASE_DIR}/execFunction.sh test-for-traces
    ${BASE_DIR}/execFunction.sh check-for-env-vars
    ${BASE_DIR}/execFunction.sh check-for-pod-metadata
    ${BASE_DIR}/execFunction.sh check-for-deploy-metadata
    echo "[run-auto-lib-injection] Completed successfully"
fi

if [ $TEST_CASE == "TestCase2" ]; then
    # Config change:
    #   - deploy app & agent
    #   - apply config
    #   - check for traces
    #   - apply different tracers config
    #   - check for traces
    echo "[run-auto-lib-injection] Deploying deployment"
    ${BASE_DIR}/execFunction.sh deploy-app-auto
    echo "[run-auto-lib-injection] Deploying agents"
    ${BASE_DIR}/execFunction.sh deploy-agents-auto
    echo "[run-auto-lib-injection] Apply default config"
    ${BASE_DIR}/execFunction.sh apply-config-auto
    echo "[run-auto-lib-injection] Running tests for default config"
    ${BASE_DIR}/execFunction.sh test-for-traces
    echo "[run-auto-lib-injection] Apply config-1"
    CONFIG_NAME=config-1 ${BASE_DIR}/execFunction.sh apply-config-auto
    echo "[run-auto-lib-injection] Running tests for config-1"
    ${BASE_DIR}/execFunction.sh test-for-traces
    CONFIG_NAME=config-1 ${BASE_DIR}/execFunction.sh check-for-env-vars
    CONFIG_NAME=config-1 ${BASE_DIR}/execFunction.sh check-for-deploy-metadata
    ${BASE_DIR}/execFunction.sh check-for-pod-metadata
    echo "[run-auto-lib-injection] Completed successfully"
fi

if [ $TEST_CASE == "TestCase3" ]; then
    # Config persistence:
    #   - deploy app & agent
    #   - apply config
    #   - check for traces
    #   - trigger unrelated rolling-update
    #   - check for traces
    echo "[run-auto-lib-injection] Deploying deployment"
    ${BASE_DIR}/execFunction.sh deploy-app-auto
    echo "[run-auto-lib-injection] Deploying agents"
    ${BASE_DIR}/execFunction.sh deploy-agents-auto
    echo "[run-auto-lib-injection] Trigger config"
    ${BASE_DIR}/execFunction.sh apply-config-auto
    echo "[run-auto-lib-injection] Running tests"
    ${BASE_DIR}/execFunction.sh test-for-traces
    ${BASE_DIR}/execFunction.sh check-for-env-vars
    ${BASE_DIR}/execFunction.sh check-for-pod-metadata
    ${BASE_DIR}/execFunction.sh check-for-deploy-metadata
    echo "[run-auto-lib-injection] Trigger unrelated rolling-update"
    ${BASE_DIR}/execFunction.sh trigger-app-rolling-update
    echo "[run-auto-lib-injection] Running tests"
    ${BASE_DIR}/execFunction.sh test-for-traces
    ${BASE_DIR}/execFunction.sh check-for-env-vars
    ${BASE_DIR}/execFunction.sh check-for-pod-metadata
    ${BASE_DIR}/execFunction.sh check-for-deploy-metadata
    echo "[run-auto-lib-injection] Completed successfully"
fi

if [ $TEST_CASE == "TestCase4" ]; then
    # Mismatching config:
    #   - deploy app & agent
    #   - apply config with non-matching cluster name
    #   - check that metadata does not exist
    echo "[run-auto-lib-injection] Deploying deployment"
    ${BASE_DIR}/execFunction.sh deploy-app-auto
    echo "[run-auto-lib-injection] Deploying agents"
    ${BASE_DIR}/execFunction.sh deploy-agents-auto
    echo "[run-auto-lib-injection] Trigger config"
    CONFIG_NAME=config-mismatch-clustername ${BASE_DIR}/execFunction.sh apply-config-auto
    echo "[run-auto-lib-injection] Running tests"
    ${BASE_DIR}/execFunction.sh check-for-no-pod-metadata
    echo "[run-auto-lib-injection] Completed successfully"
fi

if [ $TEST_CASE == "TestCase5" ]; then
    # Config change to action:disable
    #   - deploy app & agent
    #   - apply matching config
    #   - check that deployment instrumented
    #   - apply config with action:disable
    #   - check that deployment is not longer instrumented
    echo "[run-auto-lib-injection] Deploying deployment"
    ${BASE_DIR}/execFunction.sh deploy-app-auto
    echo "[run-auto-lib-injection] Deploying agents"
    ${BASE_DIR}/execFunction.sh deploy-agents-auto
    echo "[run-auto-lib-injection] Apply matching config"
    ${BASE_DIR}/execFunction.sh apply-config-auto
    echo "[run-auto-lib-injection] Check that deployment is instrumented"
    ${BASE_DIR}/execFunction.sh test-for-traces
    echo "[run-auto-lib-injection] Apply disabled config"
    CONFIG_NAME=config-disabled ${BASE_DIR}/execFunction.sh apply-config-auto
    echo "[run-auto-lib-injection] Running tests"
    ${BASE_DIR}/execFunction.sh check-for-disabled-pod-metadata
    echo "[run-auto-lib-injection] Completed successfully"
fi

if [ $TEST_CASE == "TestCase6" ]; then
    # Inject-all case (for batch instrumentation)
    #   - use language name "all" in RC config
    #   - all supported language libraries should be injected into the container
    #   - ensure traces are produced and the pods are modified correctly
    echo "[run-auto-lib-injection] Deploying deployment"
    ${BASE_DIR}/execFunction.sh deploy-app-auto
    echo "[run-auto-lib-injection] Deploying agents"
    ${BASE_DIR}/execFunction.sh deploy-agents-auto
    echo "[run-auto-lib-injection] Apply config"
    INJECT_ALL="1" ${BASE_DIR}/execFunction.sh apply-config-auto
    echo "[run-auto-lib-injection] Running tests"
    ${BASE_DIR}/execFunction.sh test-for-traces
    ${BASE_DIR}/execFunction.sh check-for-env-vars
    INJECT_ALL="1" ${BASE_DIR}/execFunction.sh check-for-pod-metadata
    ${BASE_DIR}/execFunction.sh check-for-deploy-metadata
    echo "[run-auto-lib-injection] Completed successfully"
fi
