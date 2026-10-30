#!/bin/bash

echo "--- PIP FREEZE ---"
python -m pip freeze
echo "------------------"

# A single worker keeps in-memory state (login sessions) consistent across requests
exec ddtrace-run gunicorn -w 1 -b 0.0.0.0:7777 --access-logfile - -k aiohttp.GunicornWebWorker main:app
