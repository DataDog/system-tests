#!/bin/bash

set -eu

mkdir /dd-tracer

install_custom_jar() {
    local jar_pattern="$1"
    local artifact_id="$2"
    local jar_count
    jar_count=$(find /binaries/ -name "${jar_pattern}" 2>/dev/null | wc -l)

    if [ "$jar_count" = 0 ]; then
        echo "Using default $artifact_id"
    elif [ "$jar_count" = 1 ]; then
        [[ "$#" -lt 3 ]] && MVN_OPTS= || MVN_OPTS="$3"
        local mvn_args=()
        if [[ -n "$MVN_OPTS" ]]; then
            read -r -a mvn_args <<< "$MVN_OPTS"
        fi
        local custom_jar
        custom_jar=$(find /binaries/ -name "${jar_pattern}")
        echo "Using custom $artifact_id: ${custom_jar}"
        mvn -Dfile="$custom_jar" -DgroupId=com.datadoghq -DartifactId="$artifact_id" \
            -Dversion=9999 -Dpackaging=jar "${mvn_args[@]}" install:install-file
    else
        echo "Too many $artifact_id within binaries folder"
        exit 1
    fi
}

[[ "$#" -eq 0 ]] && MVN_OPTS= || MVN_OPTS="$1"

# Look for custom dd-trace-api jar in custom binaries folder
install_custom_jar "dd-trace-api*.jar" "dd-trace-api" "$MVN_OPTS"

# Look for custom dd-openfeature jar in custom binaries folder
install_custom_jar "dd-openfeature*.jar" "dd-openfeature" "$MVN_OPTS"

# Look for custom dd-trace-java jar in custom binaries folder
if [ "$(find /binaries -maxdepth 1 -name 'dd-java-agent*.jar' | wc -l)" = 0 ]; then
    if [ -f /binaries/java-load-from-s3 ]; then
        GIT_REF=$(cat /binaries/java-load-from-s3)
        BUILD_URL="https://s3.us-east-1.amazonaws.com/dd-trace-java-builds/${GIT_REF}/dd-java-agent.jar"
    elif [ -f /binaries/java-load-from-release ]; then
        RELEASE_TAG=$(cat /binaries/java-load-from-release)
        BUILD_URL="https://github.com/DataDog/dd-trace-java/releases/download/${RELEASE_TAG}/dd-java-agent.jar"
    else
        BUILD_URL="https://github.com/DataDog/dd-trace-java/releases/latest/download/dd-java-agent.jar"
    fi
    echo "install from reference: $BUILD_URL"
    curl -Lf -o /dd-tracer/dd-java-agent.jar "$BUILD_URL"

elif [ "$(find /binaries -maxdepth 1 -name 'dd-java-agent*.jar' | wc -l)" = 1 ]; then
    CUSTOM_JAR=$(find /binaries -maxdepth 1 -name 'dd-java-agent*.jar')
    echo "Install local file $CUSTOM_JAR"
    cp "$CUSTOM_JAR" /dd-tracer/dd-java-agent.jar

else
    echo "Too many jar files in binaries"
    exit 1
fi

java -jar /dd-tracer/dd-java-agent.jar > /binaries/SYSTEM_TESTS_LIBRARY_VERSION

echo "Installed $(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION) java library"

echo "dd-trace version: $(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION)"
