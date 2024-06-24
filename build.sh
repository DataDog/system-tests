#!/usr/bin/env bash
set -eu

ATTEMPT=${SYSTEM_TEST_BUILD_ATTEMPTS:=1}

for ((i = 1; i <= ATTEMPT; i++)); do
    echo "== Run build script (attempt $i on $ATTEMPT) =="
    if ./utils/build/build.sh "$@"; then
        exit 0
    fi
done

echo "Build step failed after $ATTEMPT attempts"
exit 1
