#!/bin/bash

# Fail on any command failure
set -e

# Absolute path to this script, e.g. /home/user/bin/foo.sh
SCRIPT_PATH=$(readlink -f "$0")
# Absolute path this script is in, thus /home/user/bin
export BASE_DIR=$(dirname "${SCRIPT_PATH}")

echo "[run-lib-injection] Running library injection test cases"
${BASE_DIR}/execFunction.sh $LIBRARY_INJECTION_CONNECTION $LIBRARY_INJECTION_ADMISSION_CONTROLLER deploy-agents-manual
echo "[run-lib-injection] Deploying pre-modified pod "
#${BASE_DIR}/execFunction.sh $LIBRARY_INJECTION_CONNECTION $LIBRARY_INJECTION_ADMISSION_CONTROLLER deploy-app-manual
echo "[run-lib-injection] Running tests"
#${BASE_DIR}/execFunction.sh $LIBRARY_INJECTION_CONNECTION $LIBRARY_INJECTION_ADMISSION_CONTROLLER test-for-traces

echo "[run-lib-injection] Completed successfully"
