#!/usr/bin/env bash
set -eu
if [[ "${UDS_WEBLOG:-0}" = "1" ]]; then
    ./set-uds-transport.sh
fi

exec ./weblog
