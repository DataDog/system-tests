#!/bin/bash

arch -x86_64 python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. protos/apm_test_client.proto
# FIXME: the codegen doesn't generate the correct import path
sed -i '' -e 's/from protos/from apm_client.protos/g' protos/*.py
