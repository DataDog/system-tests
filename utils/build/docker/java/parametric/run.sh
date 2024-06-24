#!/bin/bash

# Look for custom dd-java-agent jar in custom binaries folder
DD_JAVA_AGENT=/client/tracer/dd-java-agent.jar
CUSTOM_DD_JAVA_AGENT_COUNT=$(find /binaries/dd-java-agent*.jar 2>/dev/null | wc -l)
if [ "$CUSTOM_DD_JAVA_AGENT_COUNT" = 0 ]; then
    echo "Using latest dd-java-agent $(cat /binaries/LIBRARY_VERSION)"
elif [ "$CUSTOM_DD_JAVA_AGENT_COUNT" = 1 ]; then
    CUSTOM_DD_JAVA_AGENT=$(find /binaries/dd-java-agent*.jar)
    echo "Using custom dd-java-agent: ${CUSTOM_DD_JAVA_AGENT}"
else
    echo "Too many dd-java-agent within binaries folder"
    exit 1
fi

# Enable application debug level if tracer debug flag is enabled
case $(echo "${DD_TRACE_DEBUG:-false}" | tr '[:upper:]' '[:lower:]') in
"true" | "1") export APM_TEST_CLIENT_LOG_LEVEL=debug ;;
*) ;;
esac

java -Xmx128M -javaagent:"${CUSTOM_DD_JAVA_AGENT:-$DD_JAVA_AGENT}" \
    -XX:TieredStopAtLevel=1 \
    -Ddd.jmxfetch.enabled=false \
    -Ddd.telemetry.dependency-collection.enabled=false \
    -Ddd.integration.opentelemetry.experimental.enabled=true \
    -jar target/dd-trace-java-client-1.0.0.jar
