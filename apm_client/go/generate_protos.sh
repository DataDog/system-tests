#!/bin/bash

protoc -I=.. --go_out=. --go_opt=Mprotos/apm_test_client.proto=. --go-grpc_out=. --go-grpc_opt=Mprotos/apm_test_client.proto=. ../protos/apm_test_client.proto
# protoc -I=.. --go_out=. --go-grpc_out=.  ../protos/apm_test_client.proto
