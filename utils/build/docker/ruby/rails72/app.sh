#!/bin/bash

if [[ "${SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED:-false}" == "true" ]]; then
    exec bundle exec puma -b tcp://0.0.0.0 -p 7777 -w 0
fi

exec bundle exec puma -b tcp://0.0.0.0 -p 7777 -w 1
