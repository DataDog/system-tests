FROM maven:3.9.14-eclipse-temurin-17 AS build

ARG FRAMEWORK_VERSION=latest
ENV FRAMEWORK_VERSION=${FRAMEWORK_VERSION}

WORKDIR /app

COPY utils/build/docker/java/openai_app /app

# Copy DD trace installation scripts and binaries
COPY utils/build/docker/java/install_ddtrace.sh binaries* /binaries/

RUN /binaries/install_ddtrace.sh

# Build the shadow (fat) JAR
RUN ["./gradlew", "shadowJar"]

FROM eclipse-temurin:17-jre

WORKDIR /app

COPY --from=build /binaries/SYSTEM_TESTS_LIBRARY_VERSION /binaries/SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=build /app/build/libs/single-file-server-1.0.0-all.jar /app/app.jar
COPY --from=build /dd-tracer/dd-java-agent.jar /app/dd-java-agent.jar
COPY --from=build /app/system_tests_library_version.sh /app/system_tests_library_version.sh

COPY utils/build/docker/java/app.sh /app/app.sh
RUN chmod +x /app/app.sh /app/system_tests_library_version.sh

ENV DD_TRACE_STARTUP_LOGS=true
ENV DD_ENV="test-env"
ENV DD_VERSION="1.0"

CMD ["/app/app.sh"]
