#syntax=docker/dockerfile:1.4
ARG BASE_IMAGE

FROM ${BASE_IMAGE}


COPY lib-injection/build/docker/java/dd-lib-java-init-test-app/ .

RUN DD_INSTRUMENT_SERVICE_WITH_APM=false ./gradlew build
ENV server.port=18080
ENV DD_INSTRUMENT_SERVICE_WITH_APM=true
COPY utils/build/ssi/base/healthcheck.sh /
ENTRYPOINT ["java/bin/java", "-jar", "build/libs/k8s-lib-injection-app-0.0.1-SNAPSHOT.jar"]