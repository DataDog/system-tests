FROM maven:3.9-eclipse-temurin-11 as build

WORKDIR /app

COPY ./utils/build/docker/java/spring-boot/pom.xml .
RUN mkdir /maven && mvn -Dmaven.repo.local=/maven -B dependency:go-offline

# docker build --progress=plain -f utils/build/docker/java/spring-boot.base.Dockerfile -t datadog/system-tests:spinrg-boot.base-v0 .