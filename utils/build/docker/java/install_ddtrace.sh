#!/bin/bash

set -eu

mkdir /dd-tracer

if [ $(ls /binaries/dd-java-agent*.jar | wc -l) = 0 ]; then
    BUILD_URL="https://github.com/DataDog/dd-trace-java/releases/latest/download/dd-java-agent.jar"
    echo "install from Github release: $BUILD_URL"
    curl  -Lf -o /dd-tracer/dd-java-agent.jar $BUILD_URL

elif [ $(ls /binaries/dd-java-agent*.jar | wc -l) = 1 ]; then
    echo "Install local file $(ls /binaries/dd-java-agent*.jar)"
    cp $(ls /binaries/dd-java-agent*.jar) /dd-tracer/dd-java-agent.jar

else
    echo "Too many jar files in binaries"
    exit 1
fi

java -jar /dd-tracer/dd-java-agent.jar > /binaries/SYSTEM_TESTS_LIBRARY_VERSION

echo "Installed $(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION) java library"

touch /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION
