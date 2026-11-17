FROM maven:3-eclipse-temurin-21

WORKDIR /client

# Only the pom is an input, so that editing the parametric app sources does not require a new base image.
COPY parametric/pom.xml ./pom.xml

# `mvn dependency:go-offline` misses some artifacts (transitive poms, version ranges metadata), so run the
# real build against a dummy spring-boot app to fill the local repository. Consumers can then run maven offline.
RUN mkdir -p /maven src/main/java/warmup \
 && printf 'package warmup;\npublic class Warmup {\n    public static void main(String[] args) {}\n}\n' > src/main/java/warmup/Warmup.java \
 && mvn -Dmaven.repo.local=/maven -B package \
 && rm -rf /client/*
