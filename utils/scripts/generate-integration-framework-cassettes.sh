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

./run.sh INTEGRATION_FRAMEWORKS \
    --generate-cassettes \
    "$@" \
    -v

echo ""
echo "Cassettes generated in tests/integration_frameworks/utils/vcr-cassettes"
echo "Review the cassettes and commit them if they look correct"