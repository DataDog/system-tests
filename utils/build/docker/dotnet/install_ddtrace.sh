#!/bin/bash
set -eu

cd /binaries

get_latest_release() {
    curl "https://api.github.com/repos/$1/releases/latest" | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/';
}

mkdir -p /opt/datadog

if [ $(ls /binaries/Datadog.Trace.ClrProfiler.Native.so | wc -l) = 1 ]; then
    echo "Install ddtrace from local folder"
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
