#!/bin/bash

if [ "${UDS_WEBLOG:-}" = "1" ]; then
    ./set-uds-transport.sh
fi

./myproject --server.port=7777
