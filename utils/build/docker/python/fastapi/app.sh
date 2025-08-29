#!/bin/bash

python --version
python -m pip freeze
ddtrace-run uvicorn main:app --host 0.0.0.0 --port 7777 --log-config=log_conf.yaml