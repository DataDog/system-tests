#!/bin/bash

set -eu

socat TCP-LISTEN:8127,fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:8126 &

exec /lambda-entrypoint.sh "$_HANDLER"
