#!/bin/bash
set -eu

cd /binaries

get_latest_release() {
    curl "https://api.github.com/repos/$1/releases/latest" | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/'
}

mkdir -p /opt/datadog

if [ $(ls /binaries/Datadog.Trace.ClrProfiler.Native.so | wc -l) = 1 ]; then
    echo "Install from local folder"
    cp -r /binaries/* /opt/datadog/
else
    if [ $(ls datadog-dotnet-apm*.tar.gz | wc -l) = 1 ]; then
        echo "Install ddtrace from $(ls datadog-dotnet-apm*.tar.gz)"
    else
        echo "Install ddtrace from github releases"
        DDTRACE_VERSION="$(get_latest_release DataDog/dd-trace-dotnet)"

        if [ $(uname -m) = "aarch64" ]; then
            artifact=datadog-dotnet-apm-${DDTRACE_VERSION}.arm64.tar.gz
        else
            artifact=datadog-dotnet-apm-${DDTRACE_VERSION}.tar.gz
        fi

        echo "Using artifact ${artifact}"
        curl -L https://github.com/DataDog/dd-trace-dotnet/releases/download/v${DDTRACE_VERSION}/${artifact} --output ${artifact}
    fi

    tar xzf $(ls datadog-dotnet-apm*.tar.gz) -C /opt/datadog
fi

apt-get install -y binutils #we need 'strings' command to extract assembly version which is part of binutils package
version=$(strings /opt/datadog/net6.0/Datadog.Trace.dll | egrep '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$')
echo "${version:0:-2}" >/app/SYSTEM_TESTS_LIBRARY_VERSION

LD_LIBRARY_PATH=/opt/datadog dotnet fsi --langversion:preview /binaries/query-versions.fsx

echo "dd-trace version: $(cat /app/SYSTEM_TESTS_LIBRARY_VERSION)"
echo "libddwaf version: $(cat /app/SYSTEM_TESTS_LIBDDWAF_VERSION)"
echo "appsec event rules version: $(cat /app/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION)"
