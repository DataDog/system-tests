#!/bin/bash

set -eu

cd /usr/app

BUN_ARGS=(--network-concurrency 16 --trust --linker=hoisted)

run_without_node_env () {
    (
        unset NODE_ENV
        "$@"
    )
}

install_custom_target () {
    local target=$1
    run_without_node_env bun add "${BUN_ARGS[@]}" "$target" || (sleep 30 && run_without_node_env bun add "${BUN_ARGS[@]}" "$target")
}

if [ -e /binaries/nodejs-load-from-local ]; then
    echo "using local version that will be mounted at runtime"
else
    if [ -e /binaries/nodejs-load-from-npm ]; then
        target=$(</binaries/nodejs-load-from-npm)
        echo "install from: $target"
        install_custom_target "$target"

    elif [ -e /binaries/dd-trace-js ]; then
        # bun pm pack runs prepack/prepare lifecycle hooks needed to build dd-trace-js
        target=$(cd /binaries/dd-trace-js && run_without_node_env bun pm pack --destination /usr/app --quiet)
        echo "install from local folder /binaries/dd-trace-js"
        install_custom_target "$target"

    else
        echo "install from NPM"
        install_custom_target dd-trace
    fi
fi
