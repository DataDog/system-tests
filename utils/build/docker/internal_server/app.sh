#!/bin/sh

python -m pip install fastapi[standard]==0.116.1
python -m fastapi run  --port 8089 /app/app.py