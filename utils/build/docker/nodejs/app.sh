#!/bin/bash

if [ "${UDS_WEBLOG:-}" = "1" ]; then
    ./set-uds-transport.sh
fi

set -e

if [ -e /volumes/dd-trace-js ]; then
    cd /volumes/dd-trace-js
    npm link
    cd /usr/app
    npm link dd-trace
fi
