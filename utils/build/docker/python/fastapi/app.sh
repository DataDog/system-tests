#!/bin/bash

echo "--- PIP FREEZE ---"
python -m pip freeze
echo "------------------"

ddtrace-run uvicorn main:app --host 0.0.0.0 --port 7777 --log-config=log_conf.yaml