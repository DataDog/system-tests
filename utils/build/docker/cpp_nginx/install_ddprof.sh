#!/bin/bash

#set -euo pipefail

# Checks in binary folder otherwise download from GH
ddprof_name=$(ls -1 ddprof*.xz  2> /dev/null || true)
if [ "$(echo $ddprof_name | wc -l)" -ge "2" ]; then
    echo "Clean up the folder in ${PWD}"
    exit 1
fi

curl_install=$(which curl 2> /dev/null || true)

if [ -z $curl_install ]; then
    echo "please install curl"
    exit 1
fi

if [ -z "${ddprof_name}" ] || [ ! -e "${ddprof_name}" ]; then
    echo "Could not find a version of ddprof in ${PWD}"
    tag_name=$(wget -qO- "https://api.github.com/repos/DataDog/ddprof/releases/latest" | jq -r '.tag_name' | cut -c2-)
    url_release="https://github.com/DataDog/ddprof/releases/download/v${tag_name}/ddprof-${tag_name}-amd64-linux.tar.xz"
    curl -L -O ${url_release}
    ddprof_name=$(ls ddprof*.xz)
else
    echo "using existing ddprof ${ddprof_name}"
fi

ddprof_install_path=${1-""}
if [ -z ${ddprof_install_path-:""} ]; then
    echo "Specify install path"
    ddprof_install_path="/usr/local/bin/"
    echo "Override install path to: ${ddprof_install_path}"
fi

tar xvf ${ddprof_name} ddprof/bin/ddprof -O > ${ddprof_install_path}/ddprof
chmod +x ${ddprof_install_path}/ddprof

SYSTEM_TESTS_PROFILER_VERSION=$(${ddprof_install_path}/ddprof --version)
echo "Profiler version: $(echo ${SYSTEM_TESTS_PROFILER_VERSION})"
