FROM ghcr.io/graalvm/native-image-community:22.0.0

ENV JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=true"

COPY --from=maven:3.9.9-eclipse-temurin-17 /usr/share/maven /usr/share/maven
# install_ddtrace.sh runs `mvn` to install custom jars from binaries/
ENV PATH="/usr/share/maven/bin:${PATH}"

WORKDIR /app

# Only the pom is an input, so that editing the weblog sources does not require a new base image.
COPY spring-boot-3-native/pom.xml ./pom.xml

# `mvn dependency:go-offline` misses some artifacts (transitive poms, version ranges metadata, the spring AOT and
# native build tools, the GraalVM reachability metadata), so run the real native build against a dummy spring boot
# app to fill the local repository. Its main class must be the pom's start-class. The with-profiling and
# without-profiling profiles only add build args (and the tracer, not installed yet), so they are not needed here.
# Also warm up the install plugin used by install_ddtrace.sh for custom jars. Consumers can then run maven offline.
RUN mkdir -p /maven src/main/java/com/datadoghq/springbootnative \
 && printf 'package com.datadoghq.springbootnative;\nimport org.springframework.boot.SpringApplication;\nimport org.springframework.boot.autoconfigure.SpringBootApplication;\n@SpringBootApplication\npublic class App {\n    public static void main(String[] args) {\n        SpringApplication.run(App.class, args);\n    }\n}\n' > src/main/java/com/datadoghq/springbootnative/App.java \
 && /usr/share/maven/bin/mvn -Dmaven.repo.local=/maven -B -Pnative native:compile \
 && /usr/share/maven/bin/mvn -Dmaven.repo.local=/maven -B install:install-file -Dfile=pom.xml -DgroupId=system-tests -DartifactId=warmup -Dversion=0 -Dpackaging=pom \
 && rm -rf /maven/system-tests /app/*
