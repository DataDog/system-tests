# Generate protobuf Python source files for the testing client.
# This test client is used to make requests to each of the language-specific
# grpc servers.
# Requires protoc to be installed on the host.

python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. protos/apm_test_client.proto
# FIXME: the codegen doesn't generate the correct import path
Get-ChildItem ".\protos\*.py" | % { (Get-Content $_.FullName) -replace 'from protos','from utils.parametric.protos' | Set-Content $_.FullName }
