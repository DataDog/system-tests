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

FROM maven:3.8-jdk-8 as build

RUN apt-get update && \
	apt-get install -y libarchive-tools

WORKDIR /app

COPY ./utils/build/docker/java/spring-boot/pom.xml .

COPY ./utils/build/docker/java/spring-boot/src ./src
RUN mvn -Popenliberty package


FROM eclipse-temurin:11-jre

WORKDIR /app
COPY --from=agent /LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=agent /LIBDDWAF_VERSION SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=agent /APPSEC_EVENT_RULES_VERSION SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=build /app/target/myproject-0.0.1-SNAPSHOT.jar /app/app.jar
COPY --from=agent /dd-java-agent.jar .

ENV DD_JMXFETCH_ENABLED=false
ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'

ENV JVM_ARGS='-javaagent:/app/dd-java-agent.jar'

RUN echo "#!/bin/bash\njava -Xmx362m -jar /app/app.jar" > app.sh
RUN chmod +x app.sh
CMD [ "/app/app.sh" ]
