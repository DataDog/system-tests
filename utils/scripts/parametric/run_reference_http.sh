#!/bin/bash


PORT="${PORT:=8000}"

pushd ../../../utils/build/docker/python_http/parametric
    APM_TEST_CLIENT_SERVER_PORT=$PORT python -m apm_test_client
popd || exit
