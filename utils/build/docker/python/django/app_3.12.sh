#!/bin/bash

if [ "${UDS_WEBLOG:-}" = "1" ]; then
    ./set-uds-transport.sh
fi

ddtrace-run gunicorn -w 1 -b 0.0.0.0:7777 --header-map dangerous --access-logfile - django_app.wsgi -k gevent