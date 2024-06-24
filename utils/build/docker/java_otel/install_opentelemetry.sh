#!/bin/bash

set -eu

mkdir /otel-tracer

# shellcheck disable=SC2012
if [ "$(ls /binaries/opentelemetry-javaagent*.jar | wc -l)" = 0 ]; then
    BUILD_URL="https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/latest/download/opentelemetry-javaagent.jar"
    echo "install from Github release: $BUILD_URL"
    curl -Lf -o /otel-tracer/opentelemetry-javaagent.jar $BUILD_URL

elif [ "$(ls /binaries/opentelemetry-javaagent*.jar | wc -l)" = 1 ]; then
    echo "Install local file $(ls /binaries/opentelemetry-javaagent*.jar)"
    cp "$(ls /binaries/opentelemetry-javaagent*.jar)" /otel-tracer/opentelemetry-javaagent.jar

else
    echo "Too many jar files in binaries"
    exit 1
fi

touch /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION
touch /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
java -jar /otel-tracer/opentelemetry-javaagent.jar >/binaries/SYSTEM_TESTS_LIBRARY_VERSION

echo "opentelemetry-javaagent version: $(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION)"
