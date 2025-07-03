#!/bin/bash

uwsgi -p 1 --enable-threads --threads 16 --listen 100 --http :7778 -w app:app --lazy --lazy-apps --master -b 65535 --catch-exceptions --thunder-lock --import=ddtrace.bootstrap.sitecustomize &

nginx -g "daemon off;"