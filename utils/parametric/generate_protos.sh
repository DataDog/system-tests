#!/bin/bash

SEDOPTION=("-i")
if [[ $OSTYPE == "darwin"* ]]; then
    SEDOPTION=("-i ''")
fi

python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. protos/apm_test_client.proto
sed "${SEDOPTION[@]}" -e 's/from protos/from utils.parametric.protos/g' protos/*.py
