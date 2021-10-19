#!/bin/bash

set -eu
    
cd /binaries

if [ $(ls nodejs-load-from-npm | wc -l) = 0 ]; then
    echo "install from NPM"
    cd /usr/app
    npm install dd-trace
else
    echo "install from $(cat nodejs-load-from-npm)"
    cd /usr/app
    npm install "$(cat /binaries/nodejs-load-from-npm)"
fi

npm list | grep dd-trace | sed 's/.*@//' | sed 's/ .*//'> /usr/app/SYSTEM_TESTS_LIBRARY_VERSION

echo "dd-trace version: $(cat /usr/app/SYSTEM_TESTS_LIBRARY_VERSION)"
