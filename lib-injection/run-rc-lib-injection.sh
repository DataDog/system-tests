#!/bin/bash

# Fail on any command failure
set -e

# Absolute path to this script, e.g. /home/user/bin/foo.sh
SCRIPT_PATH=$(readlink -f "$0")
# Absolute path this script is in, thus /home/user/bin
export BASE_DIR=$(dirname "${SCRIPT_PATH}")

echo "[run-lib-injection] Running library injection test cases"
${BASE_DIR}/execFunction.sh $REMOTE_CONFIG deploy-agents
echo "[run-lib-injection] Deploying deployment"
${BASE_DIR}/execFunction.sh $REMOTE_CONFIG deploy-app
echo "[run-lib-injection] Running tests"
${BASE_DIR}/execFunction.sh $REMOTE_CONFIG test-for-traces

echo "[run-lib-injection] Completed successfully"
