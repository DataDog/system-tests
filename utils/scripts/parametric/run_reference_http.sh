#!/bin/bash
# shellcheck disable=SC1091

PORT="${PORT:=8000}"

source "$PWD/venv/bin/activate"

pushd "$PWD/utils/build/docker/python_http/parametric" || exit
APM_TEST_CLIENT_SERVER_PORT=$PORT python -m apm_test_client
popd || exit
