#!/bin/bash

set -eu

echo 'starting app'

if [ "${UDS_WEBLOG:-0}" = "1" ]; then
    ./set-uds-transport.sh
fi

if ( ! dotnet app.dll); then
    echo recovering dump to /var/log/system-tests/dumps
    mkdir -p /var/log/system-tests/dumps
    find /tmp -name 'coredump*' -exec cp '{}' /var/log/system-tests/dumps \;
    chmod -R 644 /var/log/system-tests/dumps/* || true
fi
