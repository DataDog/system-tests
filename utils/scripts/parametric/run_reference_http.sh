#!/bin/bash


PORT="${PORT:=8000}"

pushd apps/python_http/
    APM_TEST_CLIENT_SERVER_PORT=$PORT python -m apm_test_client
popd
