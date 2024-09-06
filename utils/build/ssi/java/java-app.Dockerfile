#syntax=docker/dockerfile:1.4
ARG BASE_IMAGE

FROM ${BASE_IMAGE}

COPY lib-injection/build/docker/java/jdk7-app/ .
RUN java/bin/javac *.java

ENV DD_INSTRUMENT_SERVICE_WITH_APM=true
COPY utils/build/ssi/base/healthcheck.sh /

ENTRYPOINT ["java/bin/java", "-cp", ".", "SimpleHttpServer"]