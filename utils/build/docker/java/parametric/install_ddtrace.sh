#!/bin/bash

MAVEN_PROFILES=

# Look for custom dd-trace-api jar in custom binaries folder
CUSTOM_DD_TRACE_API_COUNT=$(find /binaries/dd-trace-api*.jar 2>/dev/null | wc -l)
if [ "$CUSTOM_DD_TRACE_API_COUNT" = 0 ]; then
    echo "Using default dd-trace-api"
elif [ "$CUSTOM_DD_TRACE_API_COUNT" = 1 ]; then
    CUSTOM_DD_TRACE_API=$(find /binaries/dd-trace-api*.jar)
    echo "Using custom dd-trace-api: ${CUSTOM_DD_TRACE_API}"
    MAVEN_PROFILES="$MAVEN_PROFILES -DcustomDdTraceApi=${CUSTOM_DD_TRACE_API}"
else
    echo "Too many dd-trace-api within binaries folder"
    exit 1
fi

# Look for custom dd-java-agent jar in custom binaries folder
CUSTOM_DD_JAVA_AGENT_COUNT=$(find /binaries/dd-java-agent*.jar 2>/dev/null | wc -l)
if [ "$CUSTOM_DD_JAVA_AGENT_COUNT" = 0 ]; then
    echo "Using latest dd-java-agent"
    wget -O /client/tracer/dd-java-agent.jar --no-cache https://github.com/DataDog/dd-trace-java/releases/latest/download/dd-java-agent.jar
elif [ "$CUSTOM_DD_JAVA_AGENT_COUNT" = 1 ]; then
    CUSTOM_DD_JAVA_AGENT=$(find /binaries/dd-java-agent*.jar)
    echo "Using custom dd-java-agent: ${CUSTOM_DD_JAVA_AGENT}"
    cp $CUSTOM_DD_JAVA_AGENT /client/tracer/dd-java-agent.jar
else
    echo "Too many dd-java-agent within binaries folder"
    exit 1
fi

java -jar /client/tracer/dd-java-agent.jar  > /client/SYSTEM_TESTS_LIBRARY_VERSION

echo "Running Maven build with profiles ${MAVEN_PROFILES}"

# shellcheck disable=SC2086
mvn -q $MAVEN_PROFILES -Dclient.protobuf.path=src/main/proto/ package

