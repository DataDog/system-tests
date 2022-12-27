#!/bin/bash

if [ ${UDS_WEBLOG:-} = "1" ]; then
    ./set-uds-transport.sh
fi

ddtrace-run gunicorn -w 1 -b 0.0.0.0:7777 --access-logfile - app:app -k gevent