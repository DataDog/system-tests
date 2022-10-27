#!/bin/bash

AGENT_COUNT=$(ls /binaries/dd-java-agent*.jar 2>/dev/null | wc -l)
if [ $AGENT_COUNT = 0 ]; then
    echo "Running default build"
    java -cp "target/*:target/lib/*" com.datadoghq.App
elif [ $AGENT_COUNT = 1 ]; then
    echo "Running custom binaries"
    java -cp "target/*:/binaries/*:target/lib/*" com.datadoghq.App
else
    echo "Too many jar files in binaries"
    exit 1
fi
