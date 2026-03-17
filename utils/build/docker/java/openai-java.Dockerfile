FROM maven:3.9.14-eclipse-temurin-17

ARG FRAMEWORK_VERSION=latest
ENV FRAMEWORK_VERSION=${FRAMEWORK_VERSION}

WORKDIR /app

COPY utils/build/docker/java/openai_app /app

RUN ["./gradlew", "init"]



# Copy DD trace installation scripts and binaries
COPY utils/build/docker/java/install_ddtrace.sh binaries* /binaries/

RUN /binaries/install_ddtrace.sh

# Build the application
RUN ["./gradlew", "build"]

# Create logs directory
RUN mkdir -p /integration-framework-tracer-logs

# Set environment variables
ENV DD_TRACE_STARTUP_LOGS=true

ENV DD_ENV="test-env"
ENV DD_VERSION="1.0"

ENV JAVA_TOOL_OPTIONS="-javaagent:/dd-tracer/dd-java-agent.jar"

# Run the application with DD Java agent
CMD ["./gradlew", "run", "--no-daemon"]
