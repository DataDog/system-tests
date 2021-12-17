#!/bin/bash

set -eu

mkdir /dd-tracer

cd /binaries

if [ $(ls dd-java-agent-*.jar | wc -l) = 0 ]; then
    echo "install from maven binary"
    basename $(ls -d -1 /maven/com/datadoghq/dd-java-agent/*/) > SYSTEM_TESTS_LIBRARY_VERSION
    cp /maven/com/datadoghq/dd-java-agent/$(cat SYSTEM_TESTS_LIBRARY_VERSION)/dd-java-agent-$(cat SYSTEM_TESTS_LIBRARY_VERSION).jar /dd-tracer/dd-java-agent.jar
else
    echo "install local file"
    ls dd-java-agent-*.jar | sed 's/[^0-9]*//' | sed -E 's/(-SNAPSHOT)?.jar//' > SYSTEM_TESTS_LIBRARY_VERSION

    cp $(ls dd-java-agent-*.jar) /dd-tracer/dd-java-agent.jar
fi

touch SYSTEM_TESTS_LIBDDWAF_VERSION