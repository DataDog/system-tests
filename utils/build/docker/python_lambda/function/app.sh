#!/bin/sh

set -eu

export DD_LAMBDA_HANDLER=handler.lambda_handler

exec /lambda-entrypoint.sh datadog_lambda.handler.handler
