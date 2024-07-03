#!/bin/bash

export PYTHONPATH='.'

source venv/bin/activate
python utils/scripts/get-image-list.py '"'$1'"' > compose.yaml

docker compose pull
