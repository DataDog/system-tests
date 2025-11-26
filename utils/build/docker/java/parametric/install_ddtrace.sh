#!/bin/bash

MAVEN_PROFILES=

configure_custom_jar() {
    local jar_pattern="$1"
    local artifact_name="$2"
    local maven_property="$3"
    local jar_count
    jar_count=$(find /binaries/ -name "${jar_pattern}" 2>/dev/null | wc -l)

    if [ "$jar_count" = 0 ]; then
        echo "Using default $artifact_name"
    elif [ "$jar_count" = 1 ]; then
        local custom_jar
        custom_jar=$(find /binaries/ -name "${jar_pattern}")
        echo "Using custom $artifact_name: ${custom_jar}"
        MAVEN_PROFILES="$MAVEN_PROFILES -D${maven_property}=${custom_jar}"
    else
        echo "Too many $artifact_name within binaries folder"
        exit 1
    fi
}

# Look for custom dd-trace-api jar in custom binaries folder
configure_custom_jar "dd-trace-api*.jar" "dd-trace-api" "customDdTraceApi"

# Look for custom dd-java-agent jar in custom binaries folder
CUSTOM_DD_JAVA_AGENT_COUNT=$(find /binaries/dd-java-agent*.jar 2>/dev/null | wc -l)
if [ "$CUSTOM_DD_JAVA_AGENT_COUNT" = 0 ]; then
    echo "Using latest dd-java-agent"
    wget -O /client/tracer/dd-java-agent.jar --no-cache https://github.com/DataDog/dd-trace-java/releases/latest/download/dd-java-agent.jar
elif [ "$CUSTOM_DD_JAVA_AGENT_COUNT" = 1 ]; then
    CUSTOM_DD_JAVA_AGENT=$(find /binaries/dd-java-agent*.jar)
    echo "Using custom dd-java-agent: ${CUSTOM_DD_JAVA_AGENT}"
    cp "$CUSTOM_DD_JAVA_AGENT" /client/tracer/dd-java-agent.jar
else
    echo "Too many dd-java-agent within binaries folder"
    exit 1
fi

java -jar /client/tracer/dd-java-agent.jar  > /client/SYSTEM_TESTS_LIBRARY_VERSION

echo "Running Maven build with profiles ${MAVEN_PROFILES}"

# shellcheck disable=SC2086
mvn -q $MAVEN_PROFILES package

# Extract application and its dependencies from class lookup performance improvements
java -Djarmode=tools -jar target/dd-trace-java-client-1.0.0.jar extract --destination application
# Warm up application and create CDS archive
APM_TEST_CLIENT_SERVER_PORT=8080 java \
  -XX:ArchiveClassesAtExit=application.jsa -Dspring.context.exit=onRefresh \
  -jar application/dd-trace-java-client-1.0.0.jar
