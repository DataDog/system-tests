#!/bin/bash

echo "--- PIP FREEZE ---"
python -m pip freeze
echo "------------------"

exec ddtrace-run python main.py
