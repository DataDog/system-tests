#!/bin/bash

set -eu

if [ $(ls /binaries/ruby-load-from-bundle-add | wc -l) = 0 ]; then
    echo "install prod version"
    echo "gem 'ddtrace'" >> Gemfile

else
    options=$(cat /binaries/ruby-load-from-bundle-add)
    echo "install from $options"
    echo $options >> Gemfile
fi

bundle install

bundle list | grep ddtrace | sed -E 's/.*\(//' | sed -E 's/[ )].*//' > SYSTEM_TESTS_LIBRARY_VERSION
echo "dd-trace version: $(cat SYSTEM_TESTS_LIBRARY_VERSION)"
