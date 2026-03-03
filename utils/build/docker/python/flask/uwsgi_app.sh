#!/bin/bash

echo "--- PIP FREEZE ---"
python -m pip freeze
echo "------------------"

exec uwsgi --ini /app/uwsgi.ini
