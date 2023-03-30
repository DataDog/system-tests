ARG APM_LIBRARY_IMAGE=apm_library_latest

FROM ghcr.io/datadog/dd-trace-java/dd-trace-java:latest as apm_library_latest

FROM eclipse-temurin:8 as apm_library_local

# Install required bsdtar
RUN apt-get update && \
	apt-get install -y libarchive-tools

# Install tracer
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /
RUN /install_ddtrace.sh

FROM $APM_LIBRARY_IMAGE as apm_library

FROM maven:3.6-jdk-11 as build

RUN apt-get update && \
	apt-get install -y libarchive-tools

WORKDIR /app

COPY ./utils/build/docker/java/spring-boot/pom.xml .
RUN mkdir /maven && mvn -Dmaven.repo.local=/maven -Pwildfly -B dependency:go-offline

COPY ./utils/build/docker/java/spring-boot/src ./src
RUN mvn -Dmaven.repo.local=/maven -Pwildfly package

FROM eclipse-temurin:11-jre

WORKDIR /app
COPY --from=apm_library /LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=apm_library /LIBDDWAF_VERSION SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=apm_library /APPSEC_EVENT_RULES_VERSION SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=build /app/target/myproject-0.0.1-SNAPSHOT-bootable.jar /app/app.jar
COPY --from=apm_library /dd-java-agent.jar .

COPY ./utils/build/docker/java/app.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV APP_EXTRA_ARGS="-Djboss.http.port=7777 -b=0.0.0.0"

CMD [ "/app/app.sh" ]
