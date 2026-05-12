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

    run_without_node_env bun add --linker=hoisted --network-concurrency 8 "$target" || run_without_node_env bun add --linker=hoisted --network-concurrency 8 "$target"
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
        bun add --linker=hoisted --network-concurrency 8 "$target" || bun add --linker=hoisted --network-concurrency 8 "$target"
    fi
fi
