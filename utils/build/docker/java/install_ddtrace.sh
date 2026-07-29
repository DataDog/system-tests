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
        local custom_jar
        custom_jar=$(find /binaries/ -name "${jar_pattern}")
        echo "Using custom $artifact_id: ${custom_jar}"
        if [[ "$#" -ge 4 ]]; then
            local pom_pattern="$4"
            local pom_count
            pom_count=$(find /binaries/ -name "${pom_pattern}" 2>/dev/null | wc -l)
            if [[ "$pom_count" = 1 ]]; then
                local custom_pom
                local custom_version
                custom_pom=$(find /binaries/ -name "${pom_pattern}")
                custom_version=$(sed -n 's:.*<version>\(.*\)</version>.*:\1:p' "$custom_pom" | head -1)
                [[ -n "$custom_version" ]] || {
                    echo "Could not read the $artifact_id version from ${custom_pom}"
                    exit 1
                }
                # shellcheck disable=SC2086
                mvn -Dfile="$custom_jar" -DpomFile="$custom_pom" $MVN_OPTS install:install-file
                printf '%s\n' "$custom_version" > "/dd-tracer/${artifact_id}-version"
                return
            elif [[ "$pom_count" -gt 1 ]]; then
                echo "Too many $artifact_id POM files within binaries folder"
                exit 1
            fi
        fi
        # shellcheck disable=SC2086
        mvn -Dfile="$custom_jar" -DgroupId=com.datadoghq -DartifactId="$artifact_id" -Dversion=9999 -Dpackaging=jar $MVN_OPTS install:install-file
    else
        echo "Too many $artifact_id within binaries folder"
        exit 1
    fi
}

[[ "$#" -eq 0 ]] && MVN_OPTS= || MVN_OPTS="$1"

# Look for custom dd-trace-api jar in custom binaries folder
install_custom_jar "dd-trace-api*.jar" "dd-trace-api" "$MVN_OPTS"

# Look for custom dd-openfeature jar in custom binaries folder
install_custom_jar "dd-openfeature*.jar" "dd-openfeature" "$MVN_OPTS" "dd-openfeature*.pom"

# Look for custom dd-trace-java jar in custom binaries folder
DD_JAVA_AGENT_COUNT=$(find /binaries/ -name "dd-java-agent*.jar" 2>/dev/null | wc -l)
if [ "$DD_JAVA_AGENT_COUNT" = 0 ]; then
    BUILD_URL="https://github.com/DataDog/dd-trace-java/releases/latest/download/dd-java-agent.jar"
    echo "install from Github release: $BUILD_URL"
    curl  -Lf -o /dd-tracer/dd-java-agent.jar $BUILD_URL

elif [ "$DD_JAVA_AGENT_COUNT" = 1 ]; then
    DD_JAVA_AGENT=$(find /binaries/ -name "dd-java-agent*.jar")
    echo "Install local file ${DD_JAVA_AGENT}"
    cp "$DD_JAVA_AGENT" /dd-tracer/dd-java-agent.jar

else
    echo "Too many jar files in binaries"
    exit 1
fi

java -jar /dd-tracer/dd-java-agent.jar > /binaries/SYSTEM_TESTS_LIBRARY_VERSION

echo "Installed $(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION) java library"

echo "dd-trace version: $(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION)"
