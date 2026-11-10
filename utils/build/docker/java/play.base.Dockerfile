FROM maven:3.6-jdk-11

ENV JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=true"

WORKDIR /app

# Only the pom is an input, so that editing the weblog sources does not require a new base image.
COPY play/pom.xml ./pom.xml

COPY maven_repository_cleanup.sh /maven_repository_cleanup.sh

# `mvn dependency:go-offline` misses some artifacts (transitive poms, version ranges metadata, and
# the scala compiler bridge), so run the real build against a dummy app to fill the local repository:
# an empty routes file, and the `Binders` package object imported by the generated router. Also warm up the
# install plugin used by install_ddtrace.sh for custom jars. Consumers can then run maven offline.
RUN mkdir -p /maven app conf \
 && printf 'package object Binders\n' > app/Binders.scala \
 && touch conf/routes conf/application.conf \
 && mvn -Dmaven.repo.local=/maven -B play2:routes-compile package play2:dist-exploded \
 && mvn -Dmaven.repo.local=/maven -B install:install-file -Dfile=pom.xml -DgroupId=system-tests -DartifactId=warmup -Dversion=0 -Dpackaging=pom \
 && rm -rf /maven/system-tests /app/* \
 && /maven_repository_cleanup.sh /maven \
 && rm /maven_repository_cleanup.sh
