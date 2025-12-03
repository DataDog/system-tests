#!/bin/bash
set -e

if [[ ! " $* " =~ " -L " ]] && [[ ! " $* " =~ " --library " ]]; then
    set -- -L python "$@"
fi

if [[ ! " $* " =~ " --weblog " ]]; then
    echo "Error: --weblog argument is required"
    echo "Usage: $0 --weblog <framework-name>@<version>"
    echo "Example: $0 --weblog openai-py@2.0.0"
    exit 1
fi

echo "Generating cassettes"
echo "⚠️  This will make real API calls"
echo ""

# Run tests - tests will be marked as xfail so pass/fail doesn't affect exit code
# All arguments are passed through
# TODO: this script needs to be updated to take in the framework name for the correct scenarios
./run.sh INTEGRATION_FRAMEWORKS \
    --generate-cassettes \
    "$@" \
    -v

echo ""
echo "Cassettes generated in tests/integration_frameworks/utils/vcr-cassettes"
echo "Review the cassettes and commit them if they look correct"