#!/bin/bash

set -euo pipefail

# Checks in binary folder otherwise download from github
ddprof_name=$(ls -1 ddprof*.xz  2> /dev/null || true)
if [ "$(echo "$ddprof_name" | wc -l)" -ge "2" ]; then
    echo "Clean up the folder in ${PWD}"
    exit 1
fi

curl_install=$(command -v curl 2> /dev/null || true)

if [ -z "$curl_install" ]; then
    echo "please install curl"
    exit 1
fi

if [ -z "${ddprof_name}" ] || [ ! -e "${ddprof_name}" ]; then
    if [ -f /binaries/cpp-nginx-ddprof-load-from-release ]; then
        tag_name=$(cut -c2- /binaries/cpp-nginx-ddprof-load-from-release)
    else
        url_releases="https://api.github.com/repos/DataDog/ddprof/releases/latest"
        echo "Could not find a version of ddprof in ${PWD}, get last release in ${url_releases}"
        tag_name=$(curl -s --retry 3 "${url_releases}" | jq -r '.tag_name' | cut -c2-)
    fi
    url_release="https://github.com/DataDog/ddprof/releases/download/v${tag_name}/ddprof-${tag_name}-amd64-linux.tar.xz"
    echo "Using $url_release"
    curl -L -O -s --retry 3 "${url_release}"
    ddprof_name=$(ls ddprof*.xz)
else
    echo "using existing ddprof ${ddprof_name}"
fi

ddprof_install_path=${1-""}
if [ -z "$ddprof_install_path" ]; then
    echo "Specify install path"
    ddprof_install_path="/usr/local/bin/"
    echo "Override install path to: ${ddprof_install_path}"
fi

ddprof_binary="${ddprof_install_path%/}/ddprof"
tar xvf "${ddprof_name}" ddprof/bin/ddprof -O > "$ddprof_binary"
chmod +x "$ddprof_binary"

SYSTEM_TESTS_PROFILER_VERSION=$("$ddprof_binary" --version)
echo "Profiler version: ${SYSTEM_TESTS_PROFILER_VERSION}"
