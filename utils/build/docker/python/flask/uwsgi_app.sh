#!/bin/bash

echo "--- PIP FREEZE ---"
python -m pip freeze
echo "------------------"

uwsgi --ini /app/uwsgi.ini
