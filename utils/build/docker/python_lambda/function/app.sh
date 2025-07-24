#!/bin/sh

set -eu

export DD_LAMBDA_HANDLER=handler.lambda_handler

socat TCP-LISTEN:8127,reuseaddr,fork,bind=0.0.0.0 TCP:127.0.0.1:8126 &

exec /lambda-entrypoint.sh datadog_lambda.handler.handler
