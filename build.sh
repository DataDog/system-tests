#!/usr/bin/env bash
set -eu

ATTEMPT=${SYSTEM_TEST_BUILD_ATTEMPTS:=1}
BUILD_TIMEOUT=${SYSTEM_TEST_BUILD_TIMEOUT:=600}  # Default 10 minutes per attempt
TIMEOUT_COMMAND=$(command -v timeout || command -v gtimeout || true)

for (( i=1; i<=$ATTEMPT; i++ ))
do
    echo "== Run build script (attempt $i on $ATTEMPT) with timeout ${BUILD_TIMEOUT}s =="

    # Temporarily disable exit on error to capture the exit code
    set +e
    if [[ -n "$TIMEOUT_COMMAND" ]]; then
        "$TIMEOUT_COMMAND" "$BUILD_TIMEOUT" ./utils/build/build.sh "$@"
    else
        echo "No timeout command found; running the build without a per-attempt timeout"
        ./utils/build/build.sh "$@"
    fi
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
