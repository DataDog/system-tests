#!/bin/bash

set -e

if [ -e /volumes/dd-trace-js ]; then
    {
        mkdir -p /usr/app/node_modules
        rm -rf /usr/app/node_modules/dd-trace
        ln -s /volumes/dd-trace-js /usr/app/node_modules/dd-trace
    } > /dev/null 2>&1 || {
        echo "Error during linking dd-trace from /volumes/dd-trace-js" >&2
        exit 1
    }
fi

node -e "console.log(require('dd-trace/package.json').version)"
