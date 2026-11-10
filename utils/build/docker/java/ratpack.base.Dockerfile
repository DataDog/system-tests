FROM maven:3.9-eclipse-temurin-11

ENV JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=true"

WORKDIR /app

# Only the pom is an input, so that editing the weblog sources does not require a new base image.
COPY ratpack/pom.xml ./pom.xml

COPY maven_repository_cleanup.sh /maven_repository_cleanup.sh

# `mvn dependency:go-offline` misses some artifacts (transitive poms, version ranges metadata),
# so run the real build against a dummy source to fill the local repository. Also warm up the
# install plugin used by install_ddtrace.sh for custom jars. Consumers can then run maven offline.
RUN mkdir -p /maven src/main/java/warmup \
 && printf 'package warmup;\npublic class Warmup {}\n' > src/main/java/warmup/Warmup.java \
 && mvn -Dmaven.repo.local=/maven -B package \
 && mvn -Dmaven.repo.local=/maven -B install:install-file -Dfile=pom.xml -DgroupId=system-tests -DartifactId=warmup -Dversion=0 -Dpackaging=pom \
 && rm -rf /maven/system-tests /app/* \
 && /maven_repository_cleanup.sh /maven \
 && rm /maven_repository_cleanup.sh
