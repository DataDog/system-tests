#!/bin/bash

echo "--- PIP FREEZE ---"
python -m pip freeze
echo "------------------"

if [[ $(python -c 'import sys; print(sys.version_info >= (3,12))') == "True" ]]; then
    ddtrace-run gunicorn -w 1 -b 0.0.0.0:7777 --header-map dangerous --access-logfile - django_app.wsgi -k gevent
else
    ddtrace-run gunicorn -w 1 -b 0.0.0.0:7777 --access-logfile - django_app.wsgi -k gevent
fi
