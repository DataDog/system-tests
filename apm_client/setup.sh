#!/bin/bash

/usr/bin/python3 -m virtualenv .venv
source .venv/bin/activate
arch -x86_64 pip install --upgrade pip
arch -x86_64 pip install -r requirements.txt
