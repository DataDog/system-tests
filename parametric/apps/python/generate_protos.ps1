python -m grpc_tools.protoc -I../.. --python_out=apm_test_client/ --grpc_python_out=apm_test_client/ ../../protos/apm_test_client.proto

# FIXME: the codegen doesn't generate the correct import path
Get-ChildItem ".\apm_test_client\protos\*.py" | % { (Get-Content $_.FullName) -replace 'from protos','from apm_test_client.protos' | Set-Content $_.FullName }
