#!/usr/bin/env bash
set -eu

ATTEMPT=${SYSTEM_TEST_BUILD_ATTEMPTS:=1}
BUILD_TIMEOUT=${SYSTEM_TEST_BUILD_TIMEOUT:=600}  # Default 10 minutes per attempt

# Use timeout by default; on macOS use gtimeout from coreutils.
timeout_command="timeout"
if [ "$(uname -s)" = "Darwin" ]; then
    timeout_command="gtimeout"
fi

for (( i=1; i<=$ATTEMPT; i++ ))
do
    echo "== Run build script (attempt $i on $ATTEMPT) with timeout ${BUILD_TIMEOUT}s =="

    # Temporarily disable exit on error to capture the exit code
    set +e
    "$timeout_command" "$BUILD_TIMEOUT" "./utils/build/build.sh" "$@"
    exit_code=$?
    set -e

    if [ $exit_code -eq 0 ]; then
        exit 0
    fi

    if [ $exit_code -eq 124 ]; then
        echo "⏱️  Attempt $i timed out after ${BUILD_TIMEOUT} seconds"
    else
        echo "❌ Attempt $i failed with exit code $exit_code"
    fi
done

echo "Build step failed after $ATTEMPT attempts"
exit 1
