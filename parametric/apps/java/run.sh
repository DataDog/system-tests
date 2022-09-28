#!/bin/bash

AGENT_COUNT=$(ls /binaries/dd-java-agent*.jar 2>/dev/null | wc -l)
if [ $AGENT_COUNT = 0 ]; then
    echo "Running latest release"
    java -jar target/dd-trace-java-client-1.0.0.jar
elif [ $AGENT_COUNT = 1 ]; then
    echo "Running custom agent from binaries"
    java -cp "target/*:/binaries/*" com.datadoghq.App
else
    echo "Too many agent jar files in binaries"
    exit 1
fi
