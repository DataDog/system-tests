#!/bin/bash

set -eu
    
cd /binaries

if [ $(ls nodejs-load-from-master | wc -l) = 0 ]; then
    echo "install from NPM"
    cd /usr/app
    npm install dd-trace
else
    echo "install from github#master"
    cd /usr/app
    npm install DataDog/dd-trace-js#master
fi

npm list | grep dd-trace | sed 's/.*@//' > /usr/app/SYSTEM_TESTS_LIBRARY_VERSION
