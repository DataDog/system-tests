#! /bin/bash

cd "$(dirname "${BASH_SOURCE[0]}")"

# you might need to adapt this command to use the right version of protoc
protoc \
--csharp_out=../dotnet/weblog/Models/ \
--java_out=../java/spring-boot/src/main/java/com/datadoghq/system_tests/springboot/ \
message.proto

cd -