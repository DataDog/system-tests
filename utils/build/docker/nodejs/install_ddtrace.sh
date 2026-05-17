#!/bin/bash

set -eu

cd /usr/app

BUN_ARGS=(--network-concurrency 8 --trust --linker=hoisted)

run_without_node_env () {
    (
        unset NODE_ENV
        "$@"
    )
}

if [ -e /binaries/nodejs-load-from-local ]; then
    echo "using local version that will be mounted at runtime"
else
    if [ -e /binaries/nodejs-load-from-npm ]; then
        target=$(</binaries/nodejs-load-from-npm)
        echo "install from: $target"
        run_without_node_env bun add "${BUN_ARGS[@]}" "$target" || run_without_node_env bun add "${BUN_ARGS[@]}" "$target"

    elif [ -e /binaries/dd-trace-js ]; then
        echo "install from local folder /binaries/dd-trace-js"
        run_without_node_env bun add "${BUN_ARGS[@]}" /binaries/dd-trace-js || run_without_node_env bun add "${BUN_ARGS[@]}" /binaries/dd-trace-js

    else
        echo "install from NPM"
        run_without_node_env bun add "${BUN_ARGS[@]}" dd-trace || run_without_node_env bun add "${BUN_ARGS[@]}" dd-trace
    fi
fi
