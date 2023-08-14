#!/usr/bin/env bash
set -eu
if [[ "${UDS_WEBLOG:-0}" = "1" ]]; then
    ./set-uds-transport.sh
fi
exec ddtrace-run gunicorn -w 1 -b 0.0.0.0:7777 --access-logfile - django_app.wsgi -k gevent
