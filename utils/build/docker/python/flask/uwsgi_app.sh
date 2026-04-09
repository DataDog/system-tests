#!/bin/bash

if [[ ${DD_APPSEC_SCA_ENABLED:-} = "1" ]]; then
    # We need a requirement with a CVE to test SCA features
    python -m pip requests==2.31.0
fi

echo "--- PIP FREEZE ---"
python -m pip freeze
echo "------------------"

exec uwsgi --ini /app/uwsgi.ini
