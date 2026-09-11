#!/bin/bash

echo "--- PIP FREEZE ---"
python -m pip freeze
echo "------------------"

exec ddtrace-run uvicorn main:app --host 0.0.0.0 --port 7777 --loop uvloop --log-config=log_conf.yaml
