#!/bin/bash

set -eu
    
cd /binaries

if [ $(ls ruby-load-from-master | wc -l) = 0 ]; then
    echo "install prod version"
    cd /app
    bundle add ddtrace
    gem list | grep ddtrace | sed  's/ddtrace (//' | sed 's/)//' > SYSTEM_TESTS_LIBRARY_VERSION
else
    echo "install from github#master"
    cd /app
    bundle add ddtrace --git "https://github.com/Datadog/dd-trace-rb" --branch "master"
    echo "DataDog/dd-trace-rb#master" > SYSTEM_TESTS_LIBRARY_VERSION
fi

more Gemfile