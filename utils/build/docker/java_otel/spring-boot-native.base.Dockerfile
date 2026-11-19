FROM maven:3.9.9-eclipse-temurin-17-focal

# Install required bsdtar
RUN apt-get update && \
	apt-get install -y libarchive-tools && \
	rm -rf /var/lib/apt/lists/*

# Used by spring-boot-native/pom.xml to select the opentelemetry-bom version
ENV OTEL_VERSION="1.26.0"

WORKDIR /app

# Only the pom is an input, so that editing the weblog sources does not require a new base image.
COPY spring-boot-native/pom.xml ./pom.xml

# `mvn dependency:go-offline` misses some artifacts (transitive poms, plugins dependencies), so run the real build
# against a dummy app (with a main class for the spring-boot repackaging) to fill the local repository.
# Consumers can then run maven offline.
RUN mkdir -p /maven src/main/java/warmup \
 && printf 'package warmup;\npublic class Warmup {\n    public static void main(String[] args) {}\n}\n' > src/main/java/warmup/Warmup.java \
 && mvn -Dmaven.repo.local=/maven -B package \
 && rm -rf /app/*
