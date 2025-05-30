#!/bin/bash

set -e

if [ -e /volumes/dd-trace-js ]; then
    {
        cd /volumes/dd-trace-js
        npm link
        cd /usr/app
        npm link dd-trace
    } > /dev/null 2>&1 || {
        echo "Error during linking dd-trace from /volumes/dd-trace-js" >&2
        exit 1
    }
fi

node -e "console.log(require('dd-trace/package.json').version)"
