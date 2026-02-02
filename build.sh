#!/usr/bin/env bash
set -eu

ATTEMPT=${SYSTEM_TEST_BUILD_ATTEMPTS:=1}
BUILD_TIMEOUT=${SYSTEM_TEST_BUILD_TIMEOUT:=600}  # Default 10 minutes per attempt

for (( i=1; i<=$ATTEMPT; i++ ))
do
    echo "== Run build script (attempt $i on $ATTEMPT) with timeout ${BUILD_TIMEOUT}s =="
    if timeout "$BUILD_TIMEOUT" ./utils/build/build.sh "$@"; then
        exit 0
    fi

    exit_code=$?
    if [ $exit_code -eq 124 ]; then
        echo "⏱️  Attempt $i timed out after ${BUILD_TIMEOUT} seconds"
    else
        echo "❌ Attempt $i failed with exit code $exit_code"
    fi
done

echo "Build step failed after $ATTEMPT attempts"
exit 1
