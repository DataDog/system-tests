#!/bin/bash

echo "--- PIP FREEZE ---"
python -m pip freeze
echo "------------------"

if [[ ${UDS_WEBLOG:-} = "1" ]]; then
    ./set-uds-transport.sh
fi

gunicorn_args=()
if [[ ${SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED:-} = "true" ]]; then
    export DD_FFE_INTAKE_HEARTBEAT_INTERVAL=5
    gunicorn_args+=(--config python:direct_evp_gunicorn)
fi

# CAVEAT: to debug the Python App, use these lines
# export FLASK_APP=app
# ddtrace-run flask run --no-reload --host=0.0.0.0 --port=7777
exec ddtrace-run gunicorn "${gunicorn_args[@]}" -w 1 --threads 1 -b 0.0.0.0:7777 --access-logfile - app:app -k gevent
