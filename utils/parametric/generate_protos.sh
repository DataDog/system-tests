#!/bin/bash

python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. protos/apm_test_client.proto
sed -i '' -e 's/from protos/from utils.parametric.protos/g' protos/*.py
