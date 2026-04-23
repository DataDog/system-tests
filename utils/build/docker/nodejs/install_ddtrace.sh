#!/bin/bash

set -eu

cd /usr/app

run_without_node_env () {
    (
        unset NODE_ENV
        "$@"
    )
}

install_custom_target () {
    local target=$1

    run_without_node_env npm install "$target" || run_without_node_env npm install "$target"
}

if [ -e /binaries/nodejs-load-from-local ]; then
    echo "using local version that will be mounted at runtime"
else
    if [ -e /binaries/nodejs-load-from-npm ]; then
        target=$(</binaries/nodejs-load-from-npm)
        echo "install from: $target"
        install_custom_target "$target"

    elif [ -e /binaries/dd-trace-js ]; then
        target=$(run_without_node_env npm pack /binaries/dd-trace-js)
        echo "install from local folder /binaries/dd-trace-js"
        install_custom_target "$target"

    else
        target="dd-trace"
        echo "install from NPM"
        npm install "$target" || npm install "$target"
    fi

    node -e "process.stdout.write(require('dd-trace/package.json').version)" > /system-tests-library-version
fi
