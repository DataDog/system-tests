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

SYSTEM_TESTS_LIBRARY_VERSION=$(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION)

if [[ $SYSTEM_TESTS_LIBRARY_VERSION == 0.10* ]]; then
    echo "1.3.1" > /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
elif [[ $SYSTEM_TESTS_LIBRARY_VERSION == 0.99* ]]; then
    echo "1.3.1" > /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
elif [[ $SYSTEM_TESTS_LIBRARY_VERSION == 0.98* ]]; then
    echo "1.2.6" > /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
elif [[ $SYSTEM_TESTS_LIBRARY_VERSION == 0.97* ]]; then
    echo "1.2.6" > /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
elif [[ $SYSTEM_TESTS_LIBRARY_VERSION == 0.96* ]]; then
  echo "1.2.5" > /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

else
  bsdtar -O - -xf /dd-tracer/dd-java-agent.jar appsec/default_config.json | \
    grep rules_version | head -1 | awk -F'"' '{print $4;}' \
    > /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
fi

echo "dd-trace version: $(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION)"
echo "libddwaf version: $(cat /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION)"
echo "rules version: $(cat /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION)"

