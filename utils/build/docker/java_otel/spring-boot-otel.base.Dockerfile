FROM maven:3.9-eclipse-temurin-11

WORKDIR /app

# Only the pom is an input, so that editing the weblog sources does not require a new base image.
COPY spring-boot/pom.xml ./pom.xml

# `mvn dependency:go-offline` misses some artifacts (transitive poms, protoc binaries), so run the real build
# against a dummy app to fill the local repository: a main class for the spring-boot repackaging, and a grpc
# service so that protoc and its grpc plugin are downloaded. Consumers can then run maven offline.
RUN mkdir -p /maven src/main/java/warmup src/main/proto \
 && printf 'package warmup;\npublic class Warmup {\n    public static void main(String[] args) {}\n}\n' > src/main/java/warmup/Warmup.java \
 && printf 'syntax = "proto3";\npackage warmupproto;\nmessage Empty {}\nservice WarmupService {\n  rpc Call (Empty) returns (Empty);\n}\n' > src/main/proto/warmup.proto \
 && mvn -Dmaven.repo.local=/maven -B package \
 && rm -rf /app/*
