# Generate the protobuf source files for the grpc client
# Requires protoc to be installed on the host.
protoc --proto_path=../.. --go_out=. --go_opt=Mprotos/apm_test_client.proto=. --go-grpc_out=. --go-grpc_opt=Mprotos/apm_test_client.proto=. ../../protos/apm_test_client.proto
# FIXME: the generated *.pb.go are given a package of __, so rewrite this to the main package
Get-ChildItem "*.pb.go" | % { (Get-Content $_.FullName) -replace 'package __','package main' | Set-Content $_.FullName }
