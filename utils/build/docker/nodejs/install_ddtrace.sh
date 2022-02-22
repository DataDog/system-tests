#!/bin/bash

set -eu

cd /binaries

if [ -e "/binaries/dd-trace-js" ]; then
    echo "Install from local folder /binaries/dd-trace-js"
    cd /usr/app
    npm install "$(npm pack /binaries/dd-trace-js)"

elif [ $(ls nodejs-load-from-npm | wc -l) = 0 ]; then
    echo "install from NPM"
    cd /usr/app
    npm install dd-trace

else
    echo "install from $(cat nodejs-load-from-npm)"
    cd /usr/app
    npm install "$(cat /binaries/nodejs-load-from-npm)"
fi

npm list | grep dd-trace | sed 's/.*@//' | sed 's/ .*//'> /usr/app/SYSTEM_TESTS_LIBRARY_VERSION
touch SYSTEM_TESTS_LIBDDWAF_VERSION

echo "dd-trace version: $(cat /usr/app/SYSTEM_TESTS_LIBRARY_VERSION)"
