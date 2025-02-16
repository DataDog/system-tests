#! /bin/bash

cd "$(dirname "${BASH_SOURCE[0]}")"

protoc \
--csharp_out=../dotnet/weblog/Models/ \
--java_out=../java/spring-boot/src/main/java/com/datadoghq/system_tests/springboot/ \
message.proto

cd -