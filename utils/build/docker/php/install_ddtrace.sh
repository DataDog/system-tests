#!/bin/bash

set -eu

cd /binaries

get_latest_release() {
    wget -qO- "https://api.github.com/repos/$1/releases/latest" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/';
}

if [ $(ls *.apk | wc -l) = 0 ]; then
    echo "Install ddtrace from github releases"
    DDTRACE_VERSION="$(get_latest_release DataDog/dd-trace-php)"
    wget -O datadog-php-tracer_${DDTRACE_VERSION}_noarch.apk https://github.com/DataDog/dd-trace-php/releases/download/${DDTRACE_VERSION}/datadog-php-tracer_${DDTRACE_VERSION}_noarch.apk
    apk add datadog-php-tracer_${DDTRACE_VERSION}_noarch.apk --allow-untrusted
elif [ $(ls *.apk | wc -l) = 1 ]; then
    echo "Install ddtrace from $(ls *.apk)"
    apk add $(ls *.apk) --allow-untrusted
else
    echo "ERROR: Found several apk files in binaries/, abort."
    exit 1
fi

cd -

apk info datadog-php-tracer | grep -m 1 description | sed 's/datadog-php-tracer-//' | sed 's/ description://' > SYSTEM_TESTS_LIBRARY_VERSION
touch SYSTEM_TESTS_LIBDDWAF_VERSION