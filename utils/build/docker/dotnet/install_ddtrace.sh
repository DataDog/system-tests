#!/bin/bash
set -eu

cd /binaries

# Secret will be available here at build time only
GITHUB_TOKEN_FILE="/run/secrets/github_token"
GITHUB_AUTH_HEADER=()
if [ -f "$GITHUB_TOKEN_FILE" ]; then
    echo "Using GitHub token for authentication"
    GITHUB_AUTH_HEADER=(-H "Authorization: Bearer $(cat "$GITHUB_TOKEN_FILE")")
fi

get_latest_release() {
    local releases
    if ! releases=$(curl --fail --retry 3 "${GITHUB_AUTH_HEADER[@]}" "https://api.github.com/repos/$1/releases/latest"); then
        echo "Failed to get latest release"
        exit 1
    fi
    echo "$releases" | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/';
}

mkdir -p /opt/datadog

native_file_count=$(find /binaries -maxdepth 1 -name 'Datadog.Trace.ClrProfiler.Native.so' | wc -l)
if [ "$native_file_count" = 1 ]; then
    echo "Install ddtrace from local folder"
    cp -r /binaries/* /opt/datadog/
else
    tarball_count=$(find /binaries -maxdepth 1 -name 'datadog-dotnet-apm*.tar.gz' | wc -l)
    if [ "$tarball_count" = 1 ]; then
        echo "Install ddtrace from $(find /binaries -maxdepth 1 -name 'datadog-dotnet-apm*.tar.gz')"
    else
        echo "Install ddtrace from github releases"
        if [ -f /binaries/dotnet-load-from-release ]; then
            DDTRACE_VERSION="$(cat /binaries/dotnet-load-from-release)"
            DDTRACE_VERSION="${DDTRACE_VERSION#v}"
        elif ! DDTRACE_VERSION="$(get_latest_release DataDog/dd-trace-dotnet)"; then
            echo "Failed to get latest release version"
            exit 1
        fi

        if [ "$(uname -m)" = "aarch64" ]; then
            artifact=datadog-dotnet-apm-${DDTRACE_VERSION}.arm64.tar.gz
        else
            artifact=datadog-dotnet-apm-${DDTRACE_VERSION}.tar.gz
        fi

        echo "Using artifact ${artifact}"
        curl -L --fail "${GITHUB_AUTH_HEADER[@]}" "https://github.com/DataDog/dd-trace-dotnet/releases/download/v${DDTRACE_VERSION}/${artifact}" --output "${artifact}"
    fi

    tarball=$(find /binaries -maxdepth 1 -name 'datadog-dotnet-apm*.tar.gz')
    tar xzf "$tarball" -C /opt/datadog
fi
