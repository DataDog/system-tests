FROM maven:3-eclipse-temurin-21

WORKDIR /client
RUN mkdir ./tracer
COPY utils/build/docker/java/parametric/src src
COPY utils/build/docker/java/parametric/install_ddtrace.sh .
COPY utils/build/docker/java/parametric/pom.xml .
COPY binaries /binaries
RUN bash install_ddtrace.sh
COPY utils/build/docker/java/parametric/run.sh .
RUN mkdir /parametric-tracer-logs
