#!/bin/bash

if [ ! -f apm_test_client.proto ]; then
    cp ../../../../parametric/protos/apm_test_client.proto .
fi

grpc_tools_ruby_protoc -I . --ruby_out=./ --grpc_out=./ ./apm_test_client.proto
