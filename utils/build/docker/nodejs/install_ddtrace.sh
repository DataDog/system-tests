#!/bin/bash

set -eu

cd /usr/app

if [ -e /binaries/nodejs-load-from-local ]; then
    echo "using local version that will be mounted at runtime"
else
    if [ -e /binaries/nodejs-load-from-npm ]; then
        target=$(</binaries/nodejs-load-from-npm)
        echo "install from: $target"

    elif [ -e /binaries/dd-trace-js ]; then
        target=$(npm pack /binaries/dd-trace-js)
        echo "install from local folder /binaries/dd-trace-js"

    else
        target="dd-trace"
        echo "install from NPM"
    fi

    npm install $target
fi

# nodejs uses the next API to get the library version. See https://github.com/DataDog/system-tests/issues/2799
echo "0.0.0" > SYSTEM_TESTS_LIBRARY_VERSION
echo "0.0.0" > SYSTEM_TESTS_LIBDDWAF_VERSION
echo "0.0.0" > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
