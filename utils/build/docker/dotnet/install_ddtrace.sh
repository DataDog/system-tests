#!/bin/bash
set -eu

cd /binaries

get_latest_release() {
    curl "https://api.github.com/repos/$1/releases/latest" | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/';
}

if [ $(ls datadog-dotnet-apm-*.tar.gz | wc -l) = 1 ]; then
    echo "Install ddtrace from $(ls datadog-dotnet-apm-*.tar.gz)"
else
    echo "Install ddtrace from github releases"
    DDTRACE_VERSION="$(get_latest_release DataDog/dd-trace-dotnet)"
    curl -L https://github.com/DataDog/dd-trace-dotnet/releases/download/v${DDTRACE_VERSION}/datadog-dotnet-apm-${DDTRACE_VERSION}.tar.gz --output datadog-dotnet-apm-${DDTRACE_VERSION}.tar.gz
fi

ls datadog-dotnet-apm-*.tar.gz > /app/SYSTEM_TESTS_LIBRARY_VERSION

mkdir -p /opt/datadog
tar xzf $(ls datadog-dotnet-apm-*.tar.gz) -C /opt/datadog

LD_LIBRARY_PATH=/opt/datadog dotnet fsi --langversion:preview /binaries/query-versions.fsx

echo "dd-trace version: $(cat /app/SYSTEM_TESTS_LIBRARY_VERSION)"
echo "libddwaf version: $(cat /app/SYSTEM_TESTS_LIBDDWAF_VERSION)"
echo "appsec event rules version: $(cat /app/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION)"