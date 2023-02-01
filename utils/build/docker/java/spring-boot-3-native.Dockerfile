
ARG TRACER_IMAGE=agent_local

#TODO RMM: The images will be in dd-trace-java repository. Now for tests purposes we are using system-tests repository
FROM ghcr.io/datadog/system-tests/dd-trace-java:latest_snapshot as agent_latest_snapshot

FROM ghcr.io/datadog/system-tests/dd-trace-java:latest as agent_latest

FROM eclipse-temurin:8 as agent_local

# Install required bsdtar
RUN apt-get update && \
	apt-get install -y libarchive-tools

# Install tracer
COPY ./utils/build/docker/java/install_ddtrace.sh binaries* /
RUN /install_ddtrace.sh


FROM $TRACER_IMAGE as agent


FROM ghcr.io/graalvm/graalvm-ce:ol7-java17-22.3.0 as build

# Install maven
RUN curl https://archive.apache.org/dist/maven/maven-3/3.8.6/binaries/apache-maven-3.8.6-bin.tar.gz --output /opt/maven.tar.gz && \
	tar xzvf /opt/maven.tar.gz --directory /opt && \
	rm /opt/maven.tar.gz

WORKDIR /app

# Copy application sources and cache dependencies
COPY ./utils/build/docker/java/spring-boot-3-native/pom.xml .
RUN /opt/apache-maven-3.8.6/bin/mvn -P native -B dependency:go-offline 
COPY ./utils/build/docker/java/spring-boot-3-native/src ./src

# Copy tracer
COPY --from=agent /dd-tracer/dd-java-agent.jar .

# Build native application
RUN /opt/apache-maven-3.8.6/bin/mvn -Pnative native:compile

FROM ubuntu

WORKDIR /app
COPY --from=agent /binaries/SYSTEM_TESTS_LIBRARY_VERSION SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=agent /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=agent /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=build /app/target/myproject .

ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'

RUN echo "#!/bin/bash\n/app/myproject --server.port=7777" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
