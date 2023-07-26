#!/bin/bash

if [ ! -f apm_test_client.proto ]; then
  cp ../../protos/apm_test_client.proto .
fi

gem install grpc-tools

grpc_tools_ruby_protoc \
  -I . \
  --ruby_out=./ \
  --grpc_out=./ ./apm_test_client.proto

gem uninstall grpc-tools
