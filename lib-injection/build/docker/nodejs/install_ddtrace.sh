#!/bin/bash

set -eu

BINARIES_DIR=$1 #/binaries
current_dir=$(pwd)
cd $BINARIES_DIR

if [ -e "dd-trace-js" ]; then
    echo "Install from local folder ${BINARIES_DIR}/dd-trace.tgz"
    cd dd-trace-js
    npm pack
    echo "Local dd-trace node version:"
    ls dd-trace-*.tgz
    mv dd-trace-*.tgz ../dd-trace.tgz
fi

cd $current_dir
