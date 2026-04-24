#!/bin/bash

if [ "${UDS_WEBLOG:-}" = "1" ]; then
    ./set-uds-transport.sh
fi

set -e

if [ -e /volumes/dd-trace-js ]; then
    mkdir -p /usr/app/node_modules
    rm -rf /usr/app/node_modules/dd-trace
    ln -s /volumes/dd-trace-js /usr/app/node_modules/dd-trace
fi

# shellcheck disable=SC2086
exec node server.js ${SYSTEM_TESTS_EXTRA_COMMAND_ARGUMENTS:-}