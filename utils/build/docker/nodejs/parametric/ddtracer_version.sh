#!/bin/bash

set -eu

if [ -z "${NODEJS_DDTRACE_MODULE}" ]; then NODEJS_DDTRACE_MODULE=dd-trace; fi

npm install
npm install "$NODEJS_DDTRACE_MODULE"
npm list --json | jq -r '.dependencies."dd-trace".version' > SYSTEM_TESTS_LIBRARY_VERSION