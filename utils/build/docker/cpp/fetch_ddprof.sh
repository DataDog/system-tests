#!/bin/bash

#set -euo pipefail

# Takes name and path to binary

ddprof_install_path=${1-""}
if [ ! -d ${ddprof_install_path-:""} ]; then
    echo "Specify install path"
    exit 1
fi
ddprof_name=${2-""}
ddprof_path=${3-""}

if [ -z ${ddprof_name-:""} ]; then
    ddprof_name="ddprof-main-amd64-unknown-linux-gnu.tar.xz"
fi

if [ -z ${ddprof_path-:""} ]; then
    ddprof_path="https://binaries.ddbuild.io/ddprof-build/"
fi

mkdir -p /tmp
pushd /tmp && which curl
cmd="curl -L -o ${ddprof_name} --insecure ${ddprof_path}/${ddprof_name}"
echo ${cmd}
eval $cmd
tar xvf ${ddprof_name} ddprof/bin/ddprof -O > ${ddprof_install_path}/ddprof
rm -f ./${ddprof_name} && chmod +x ${ddprof_install_path}/ddprof
popd
