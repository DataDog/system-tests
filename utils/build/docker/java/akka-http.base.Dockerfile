FROM maven:3.8-jdk-11

ENV JAVA_TOOL_OPTIONS="-Djava.net.preferIPv4Stack=true"

WORKDIR /app

# Only the pom is an input, so that editing the weblog sources does not require a new base image.
COPY akka-http/pom.xml ./pom.xml

# `mvn dependency:go-offline` misses some artifacts (transitive poms, version ranges metadata, the scala
# compiler), so run the real build against a dummy source to fill the local repository: the weblog is in
# scala, so the dummy source must be scala too. Also warm up the install plugin used by install_ddtrace.sh
# for custom jars. Consumers can then run maven offline.
RUN mkdir -p /maven src/main/scala/warmup \
 && printf 'package warmup\nobject Warmup {\n  def main(args: Array[String]): Unit = ()\n}\n' > src/main/scala/warmup/Warmup.scala \
 && mvn -Dmaven.repo.local=/maven -B package \
 && mvn -Dmaven.repo.local=/maven -B install:install-file -Dfile=pom.xml -DgroupId=system-tests -DartifactId=warmup -Dversion=0 -Dpackaging=pom \
 && rm -rf /maven/system-tests /app/*
