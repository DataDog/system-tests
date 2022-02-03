#!/bin/bash

set -eu

get_latest_release() {
    curl --silent "https://api.github.com/repos/$1/releases/latest" | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/';
}

mkdir /dd-tracer

cd /binaries

if [ $(ls dd-java-agent-*.jar | wc -l) = 0 ]; then
    echo "install from Github release"

    TRACER_VERSION=$(get_latest_release DataDog/dd-trace-java)
    BUILD_URL="https://github.com/DataDog/dd-trace-java/releases/download/v${TRACER_VERSION}/dd-java-agent-$TRACER_VERSION.jar"
    echo "Get $BUILD_URL"
    curl  -Lf -o /dd-tracer/dd-java-agent.jar $BUILD_URL
    echo $TRACER_VERSION > SYSTEM_TESTS_LIBRARY_VERSION

else
    echo "install local file"
    ls dd-java-agent-*.jar | sed 's/[^0-9]*//' | sed -E 's/(-SNAPSHOT)?.jar//' > SYSTEM_TESTS_LIBRARY_VERSION

    cp $(ls dd-java-agent-*.jar) /dd-tracer/dd-java-agent.jar
fi

echo "Installed $(cat SYSTEM_TESTS_LIBRARY_VERSION) java library"

touch SYSTEM_TESTS_LIBDDWAF_VERSION