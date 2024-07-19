#!/bin/bash

if [ -e /volumes/dd-trace-js ]; then
    cd /volumes/dd-trace-js
    npm link
    cd /usr/app
    npm link dd-trace
fi

./server.sh
