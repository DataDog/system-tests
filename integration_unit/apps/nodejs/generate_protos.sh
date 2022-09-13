#!/bin/bash

# Couldn't get this to work, getting `protoc-gen-js errors`
# Not even exactly sure if this is neede
protoc -I=../protos --js_out=./pb ../protos/apm_test_client.proto
