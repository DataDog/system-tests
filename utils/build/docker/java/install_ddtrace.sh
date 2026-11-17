#!/bin/bash

# Usage: install_ddtrace.sh [--with-openfeature] [MVN_OPTS]
#
# --with-openfeature: the weblog depends on com.datadoghq:dd-openfeature. The provider must have the same version as
# the agent, so either both dd-java-agent and dd-openfeature jars are in /binaries, or none of them, and the
# dd-openfeature release matching the latest agent release is installed.

set -eu

mkdir /dd-tracer

WITH_OPENFEATURE=false
if [[ "${1:-}" == "--with-openfeature" ]]; then
    WITH_OPENFEATURE=true
    shift
fi

MVN_OPTS="${1:-}"

# --retry-all-errors needs curl 7.71: on older build images (maven:3.6), only transient errors are retried
curl_retry=(--retry 3 --retry-delay 5 --retry-connrefused)
if curl --retry-all-errors --version >/dev/null 2>&1; then
    curl_retry+=(--retry-all-errors)
fi

count_jars() {
    find /binaries/ -name "$1" 2>/dev/null | wc -l
}

install_jar() {
    local jar="$1"
    local artifact_id="$2"
    # shellcheck disable=SC2086
    mvn -Dfile="$jar" -DgroupId=com.datadoghq -DartifactId="$artifact_id" -Dversion=9999 -Dpackaging=jar $MVN_OPTS install:install-file
}

install_custom_jar() {
    local jar_pattern="$1"
    local artifact_id="$2"
    local jar_count
    jar_count=$(count_jars "${jar_pattern}")

    if [ "$jar_count" = 0 ]; then
        echo "Using default $artifact_id"
    elif [ "$jar_count" = 1 ]; then
        local custom_jar
        custom_jar=$(find /binaries/ -name "${jar_pattern}")
        echo "Using custom $artifact_id: ${custom_jar}"
        install_jar "$custom_jar" "$artifact_id"
    else
        echo "Too many $artifact_id within binaries folder"
        exit 1
    fi
}

AGENT_JAR_COUNT=$(count_jars "dd-java-agent*.jar")
OPENFEATURE_JAR_COUNT=$(count_jars "dd-openfeature*.jar")

if [ "$AGENT_JAR_COUNT" -gt 1 ]; then
    echo "Too many dd-java-agent jar files in binaries"
    exit 1
fi

if [ "$WITH_OPENFEATURE" = true ] && [ "$OPENFEATURE_JAR_COUNT" -gt 1 ]; then
    echo "Too many dd-openfeature jar files in binaries"
    exit 1
fi

if [ "$WITH_OPENFEATURE" = true ] && [ "$AGENT_JAR_COUNT" != "$OPENFEATURE_JAR_COUNT" ]; then
    echo "dd-java-agent and dd-openfeature must have the same version: put both jars in binaries, or none of them" >&2
    echo "Found $AGENT_JAR_COUNT dd-java-agent jar(s) and $OPENFEATURE_JAR_COUNT dd-openfeature jar(s)" >&2
    exit 1
fi

# Look for custom dd-trace-api jar in custom binaries folder
install_custom_jar "dd-trace-api*.jar" "dd-trace-api"

if [ "$AGENT_JAR_COUNT" = 0 ]; then
    BUILD_URL="https://github.com/DataDog/dd-trace-java/releases/latest/download/dd-java-agent.jar"
    echo "install from Github release: $BUILD_URL"
    curl "${curl_retry[@]}" -Lf -o /dd-tracer/dd-java-agent.jar $BUILD_URL
else
    AGENT_JAR=$(find /binaries/ -name "dd-java-agent*.jar")
    echo "Install local file $AGENT_JAR"
    cp "$AGENT_JAR" /dd-tracer/dd-java-agent.jar
fi

java -jar /dd-tracer/dd-java-agent.jar > /binaries/SYSTEM_TESTS_LIBRARY_VERSION

echo "Installed $(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION) java library"

if [ "$WITH_OPENFEATURE" = true ]; then
    if [ "$OPENFEATURE_JAR_COUNT" = 1 ]; then
        install_custom_jar "dd-openfeature*.jar" "dd-openfeature"
    else
        # release versions are printed as X.Y.Z~<sha>
        OPENFEATURE_VERSION=$(sed -E 's/^([0-9]+\.[0-9]+\.[0-9]+).*/\1/' /binaries/SYSTEM_TESTS_LIBRARY_VERSION)
        OPENFEATURE_URL="https://repo1.maven.org/maven2/com/datadoghq/dd-openfeature/${OPENFEATURE_VERSION}/dd-openfeature-${OPENFEATURE_VERSION}.jar"
        echo "install dd-openfeature from Maven Central: $OPENFEATURE_URL"
        curl "${curl_retry[@]}" -Lf -o /dd-tracer/dd-openfeature.jar "$OPENFEATURE_URL"
        install_jar /dd-tracer/dd-openfeature.jar "dd-openfeature"
    fi
fi

echo "dd-trace version: $(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION)"
