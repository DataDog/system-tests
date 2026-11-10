FROM maven:3.9-eclipse-temurin-11

# One base image per maven profile of spring-boot/pom.xml, so that each one only holds the dependencies of its profile
ARG MAVEN_PROFILE

ENV JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=true"

WORKDIR /app

# Only the pom (and the openliberty server config, which selects the liberty features to download) are inputs,
# so that editing the weblog sources does not require a new base image.
COPY spring-boot/pom.xml ./pom.xml
COPY spring-boot/src/main/liberty/config/server.xml ./src/main/liberty/config/server.xml

# `mvn dependency:go-offline` misses some artifacts (transitive poms, version ranges metadata, protoc binaries,
# app server runtimes), so run the real build against a dummy app to fill the local repository: a main class
# for the spring-boot repackaging, a grpc service so that protoc and its grpc plugin are downloaded, and the
# web resources directory required by the payara profile. Also warm up the install plugin used by
# install_ddtrace.sh for custom jars, and the stax2-api jar shipped by the payara weblog. Consumers can then
# run maven offline.
RUN mkdir -p /maven src/main/java/warmup src/main/proto src/main/webapp-payara \
 && printf 'package warmup;\npublic class Warmup {\n    public static void main(String[] args) {}\n}\n' > src/main/java/warmup/Warmup.java \
 && printf 'syntax = "proto3";\npackage warmupproto;\nmessage Empty {}\nservice WarmupService {\n  rpc Call (Empty) returns (Empty);\n}\n' > src/main/proto/warmup.proto \
 && mvn -Dmaven.repo.local=/maven -B -P"${MAVEN_PROFILE}" package \
 && if [ "${MAVEN_PROFILE}" = payara ]; then mvn -Dmaven.repo.local=/maven -B dependency:get -Dartifact=org.codehaus.woodstox:stax2-api:4.2.1; fi \
 && mvn -Dmaven.repo.local=/maven -B install:install-file -Dfile=pom.xml -DgroupId=system-tests -DartifactId=warmup -Dversion=0 -Dpackaging=pom \
 && rm -rf /maven/system-tests /app/*
