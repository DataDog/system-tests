#!/bin/bash

if [[ ${DD_APPSEC_SCA_ENABLED:-} = "1" ]]; then
    # We need a requirement with a CVE to test SCA features
    python -m pip requests==2.31.0
fi

echo "--- PIP FREEZE ---"
python -m pip freeze
echo "------------------"

if [[ ${UDS_WEBLOG:-} = "1" ]]; then
    ./set-uds-transport.sh
fi
# CAVEAT: to debug the Python App, use these lines
# export FLASK_APP=app
# ddtrace-run flask run --no-reload --host=0.0.0.0 --port=7777
exec ddtrace-run gunicorn -w 1 --threads 1 -b 0.0.0.0:7777 --access-logfile - app:app -k gevent
