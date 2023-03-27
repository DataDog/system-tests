ARG TRACER_IMAGE=agent_local
FROM ghcr.io/datadog/dd-trace-java/dd-trace-java:latest_snapshot as agent_latest_snapshot

FROM ghcr.io/datadog/dd-trace-java/dd-trace-java:latest as agent_latest


FROM eclipse-temurin:8 as agent_local

# Install required bsdtar
RUN apt-get update && \
	apt-get install -y libarchive-tools

# Install tracer
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /
RUN /install_ddtrace.sh


FROM $TRACER_IMAGE as agent

FROM maven:3.6-jdk-11 as build

RUN apt-get update && \
	apt-get install -y libarchive-tools

WORKDIR /app

COPY ./utils/build/docker/java/jersey-grizzly2/pom.xml .
RUN mkdir /maven && mvn -Dmaven.repo.local=/maven -B dependency:go-offline

COPY ./utils/build/docker/java/jersey-grizzly2/src ./src
RUN mvn -Dmaven.repo.local=/maven package


FROM eclipse-temurin:11-jre

WORKDIR /app
COPY --from=agent /LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=agent /LIBDDWAF_VERSION SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=agent /APPSEC_EVENT_RULES_VERSION SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=build /app/target/jersey-grizzly2-1.0-SNAPSHOT.jar /app/app.jar
COPY --from=agent /dd-java-agent.jar .

COPY ./utils/build/docker/java/app.sh /app/app.sh
RUN chmod +x /app/app.sh

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_INTEGRATION_GRIZZLY_ENABLED=true

CMD [ "/app/app.sh" ]
