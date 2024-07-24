#!/bin/bash

DD_JAVA_AGENT=/client/tracer/dd-java-agent.jar
CUSTOM_DD_JAVA_AGENT_COUNT=$(find /binaries/dd-java-agent*.jar 2>/dev/null | wc -l)
if [ "$CUSTOM_DD_JAVA_AGENT_COUNT" = 0 ]; then
    java -jar $DD_JAVA_AGENT  > /client/SYSTEM_TESTS_LIBRARY_VERSION
elif [ "$CUSTOM_DD_JAVA_AGENT_COUNT" = 1 ]; then
    CUSTOM_DD_JAVA_AGENT=$(find /binaries/dd-java-agent*.jar)
    java -jar $CUSTOM_DD_JAVA_AGENT > /client/SYSTEM_TESTS_LIBRARY_VERSION
else
    echo "Too many dd-java-agent within binaries folder"
    exit 1
fi