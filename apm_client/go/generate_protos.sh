#!/bin/bash

protoc -I=.. --go_out=. --go_opt=Mprotos/apm_test_client.proto=main --go-grpc_out=. --go-grpc_opt=Mprotos/apm_test_client.proto=main ../protos/apm_test_client.proto
