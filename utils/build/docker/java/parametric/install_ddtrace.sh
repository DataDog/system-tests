#!/bin/bash

set -eu

MAVEN_PROFILES=

# Bash globs rather than `find ... 2>/dev/null | wc -l`, which counts 0 jars when `find` is missing
# globstar makes `**` recursive, nullglob makes a pattern without match expand to nothing.
shopt -s globstar nullglob

configure_custom_jar() {
    local jar_pattern="$1"
    local artifact_name="$2"
    local maven_property="$3"
    # shellcheck disable=SC2206 # the pattern must be expanded as a glob
    local jars=(/binaries/**/$jar_pattern)

    if [ "${#jars[@]}" = 0 ]; then
        echo "Using default $artifact_name"
    elif [ "${#jars[@]}" = 1 ]; then
        local custom_jar="${jars[0]}"
        echo "Using custom $artifact_name: ${custom_jar}"
        MAVEN_PROFILES="$MAVEN_PROFILES -D${maven_property}=${custom_jar}"
    else
        echo "Too many $artifact_name within binaries folder"
        exit 1
    fi
}

# Look for custom dd-trace-api jar in custom binaries folder
configure_custom_jar "dd-trace-api*.jar" "dd-trace-api" "customDdTraceApi"

# Look for custom dd-java-agent jar in custom binaries folder
CUSTOM_DD_JAVA_AGENTS=(/binaries/dd-java-agent*.jar)
CUSTOM_DD_OPENFEATURES=(/binaries/**/dd-openfeature*.jar)
CUSTOM_DD_JAVA_AGENT_COUNT=${#CUSTOM_DD_JAVA_AGENTS[@]}
CUSTOM_DD_OPENFEATURE_COUNT=${#CUSTOM_DD_OPENFEATURES[@]}

# The dd-openfeature provider must have the same version as the agent: either both jars are in binaries,
# or none of them, and the dd-openfeature release matching the latest agent release is used
if [ "$CUSTOM_DD_JAVA_AGENT_COUNT" != "$CUSTOM_DD_OPENFEATURE_COUNT" ]; then
    echo "dd-java-agent and dd-openfeature must have the same version: put both jars in binaries, or none of them" >&2
    echo "Found $CUSTOM_DD_JAVA_AGENT_COUNT dd-java-agent jar(s) and $CUSTOM_DD_OPENFEATURE_COUNT dd-openfeature jar(s)" >&2
    exit 1
fi

# Look for custom dd-openfeature jar in custom binaries folder
configure_custom_jar "dd-openfeature*.jar" "dd-openfeature" "customDdOpenfeature"

if [ "$CUSTOM_DD_JAVA_AGENT_COUNT" = 0 ]; then
    echo "Using latest dd-java-agent"
    wget -O /client/tracer/dd-java-agent.jar --no-cache https://github.com/DataDog/dd-trace-java/releases/latest/download/dd-java-agent.jar
elif [ "$CUSTOM_DD_JAVA_AGENT_COUNT" = 1 ]; then
    CUSTOM_DD_JAVA_AGENT="${CUSTOM_DD_JAVA_AGENTS[0]}"
    echo "Using custom dd-java-agent: ${CUSTOM_DD_JAVA_AGENT}"
    cp "$CUSTOM_DD_JAVA_AGENT" /client/tracer/dd-java-agent.jar
else
    echo "Too many dd-java-agent within binaries folder"
    exit 1
fi

java -jar /client/tracer/dd-java-agent.jar  > /client/SYSTEM_TESTS_LIBRARY_VERSION

if [ "$CUSTOM_DD_OPENFEATURE_COUNT" = 0 ]; then
    # release versions are printed as X.Y.Z~<sha>
    DD_OPENFEATURE_VERSION=$(sed -E 's/^([0-9]+\.[0-9]+\.[0-9]+).*/\1/' /client/SYSTEM_TESTS_LIBRARY_VERSION)
    DD_OPENFEATURE_URL="https://repo1.maven.org/maven2/com/datadoghq/dd-openfeature/${DD_OPENFEATURE_VERSION}/dd-openfeature-${DD_OPENFEATURE_VERSION}.jar"
    echo "Using dd-openfeature from Maven Central: ${DD_OPENFEATURE_URL}"
    if ! wget --tries=3 --retry-connrefused -O /client/tracer/dd-openfeature.jar --no-cache "$DD_OPENFEATURE_URL"; then
        echo "Failed to download dd-openfeature ${DD_OPENFEATURE_VERSION}" >&2
        exit 1
    fi
    MAVEN_PROFILES="$MAVEN_PROFILES -DcustomDdOpenfeature=/client/tracer/dd-openfeature.jar"
fi

echo "Running Maven build with profiles ${MAVEN_PROFILES}"

# shellcheck disable=SC2086
mvn -o -Dmaven.repo.local=/maven -q $MAVEN_PROFILES package

# Extract application and its dependencies from class lookup performance improvements
java -Djarmode=tools -jar target/dd-trace-java-client-1.0.0.jar extract --destination application
# Warm up application and create CDS archive
APM_TEST_CLIENT_SERVER_PORT=8080 java \
  -XX:ArchiveClassesAtExit=application.jsa -Dspring.context.exit=onRefresh \
  -jar application/dd-trace-java-client-1.0.0.jar
