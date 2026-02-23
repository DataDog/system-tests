#!/bin/bash

echo "--- PIP FREEZE ---"
python -m pip freeze
echo "------------------"

ddtrace-run python main.py
