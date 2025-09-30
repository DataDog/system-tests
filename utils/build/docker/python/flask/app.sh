#!/bin/bash

echo "--- PIP FREEZE ---"
python -m pip freeze
echo "------------------"

if [[ ${UDS_WEBLOG:-} = "1" ]]; then
    ./set-uds-transport.sh
fi
# CAVEAT: to debug the Python App, use these lines
# export FLASK_APP=app
# ddtrace-run flask run --no-reload --host=0.0.0.0 --port=7777
ddtrace-run gunicorn -w 1 --threads 1 -b 0.0.0.0:7777  --access-logfile - app:app -k gevent
