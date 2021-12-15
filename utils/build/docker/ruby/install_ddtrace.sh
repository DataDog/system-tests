#!/bin/bash

set -eu

if [ -e "/binaries/dd-trace-rb" ]; then
    echo "Install from folder /binaries/dd-trace-rb"
    echo "gem 'ddtrace', require: 'ddtrace/auto_instrument', path: '/binaries/dd-trace-rb'" >> Gemfile

elif [ $(ls /binaries/ruby-load-from-bundle-add | wc -l) = 0 ]; then
    echo "Install prod version"
    echo "gem 'ddtrace'" >> Gemfile

else
    options=$(cat /binaries/ruby-load-from-bundle-add)
    echo "Install from $options"
    echo $options >> Gemfile
fi

bundle install

bundle list | grep ddtrace > SYSTEM_TESTS_LIBRARY_VERSION
bundle list | grep libddwaf > SYSTEM_TESTS_LIBDDWAF_VERSION

echo "dd-trace version: $(cat SYSTEM_TESTS_LIBRARY_VERSION)"
echo "libddwaf version: $(cat SYSTEM_TESTS_LIBDDWAF_VERSION)"
