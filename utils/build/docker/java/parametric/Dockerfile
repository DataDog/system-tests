
# FROM ghcr.io/datadog/dd-trace-java/dd-trace-java:latest as apm_library_latest
FROM maven:3-jdk-8
WORKDIR /client
# COPY --from=apm_library_latest /dd-java-agent.jar ./tracer/
# COPY --from=apm_library_latest /LIBRARY_VERSION ./tracer/
RUN mkdir ./tracer/ && wget -O ./tracer/dd-java-agent.jar https://github.com/DataDog/dd-trace-java/releases/download/v1.12.1/dd-java-agent-1.12.1.jar
COPY utils/build/docker/java/parametric/src src
COPY utils/build/docker/java/parametric/build.sh .
COPY utils/build/docker/java/parametric/pom.xml .
COPY utils/build/docker/java/parametric/run.sh .
COPY tests/parametric/protos/apm_test_client.proto src/main/proto/
COPY binaries /binaries
RUN bash build.sh
