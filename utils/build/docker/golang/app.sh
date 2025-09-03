#!/bin/sh

if [ ${UDS_WEBLOG:-} = "1" ]; then
    ./set-uds-transport.sh
fi

exec ./weblog