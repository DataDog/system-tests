#!/bin/bash

# Generate the protobuf source files for the grpc client
# Requires protoc to be installed on the host.
protoc -I=../../../../parametric --go_out=. --go_opt=Mprotos/apm_test_client.proto=. --go-grpc_out=. --go-grpc_opt=Mprotos/apm_test_client.proto=. ../../../../parametric/protos/apm_test_client.proto
# FIXME: the generated *.pb.go are given a package of __, so rewrite this to the main package
sed -i '' -e 's/package __/package main/g' ./*.pb.go
