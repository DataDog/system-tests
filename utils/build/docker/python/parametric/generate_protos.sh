#!/bin/bash

python -m grpc_tools.protoc -I../.. --python_out=apm_test_client/ --grpc_python_out=apm_test_client/ ../../protos/apm_test_client.proto

# FIXME: the codegen doesn't generate the correct import path
sed -i '' -e 's/from protos/from apm_test_client.protos/g' apm_test_client/protos/*.py
