#!/bin/bash

set -eu

mkdir /dd-tracer

# Look for custom dd-trace-api jar in custom binaries folder
CUSTOM_DD_TRACE_API_COUNT=$(find /binaries/dd-trace-api*.jar 2>/dev/null | wc -l)
if [ "$CUSTOM_DD_TRACE_API_COUNT" = 0 ]; then
    echo "Using default dd-trace-api"
elif [ "$CUSTOM_DD_TRACE_API_COUNT" = 1 ]; then
    [[ "$#" -eq 0 ]] && MVN_OPTS= || MVN_OPTS="$1"
    CUSTOM_DD_TRACE_API=$(find /binaries/dd-trace-api*.jar)
    echo "Using custom dd-trace-api: ${CUSTOM_DD_TRACE_API}"
    mvn -Dfile="$CUSTOM_DD_TRACE_API" -DgroupId=com.datadoghq -DartifactId=dd-trace-api -Dversion=9999 -Dpackaging=jar $MVN_OPTS install:install-file
else
    echo "Too many dd-trace-api within binaries folder"
    exit 1
fi

# Look for custom dd-trace-java jar in custom binaries folder
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

SYSTEM_TESTS_LIBRARY_VERSION=$(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION)

echo "dd-trace version: $(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION)"



#Install Antithesis coverage instrumentation
mkdir -p /opt/antithesis/catalog
ln -s /dd-tracer /opt/antithesis/catalog
ln -s /app /opt/antithesis/catalog

wget https://repo1.maven.org/maven2/com/antithesis/ffi/1.4.4/ffi-1.4.4.jar -O antithesis-ffi-1.4.4.jar

# Unzip dd-java-agent.jar
unzip -q /dd-tracer/dd-java-agent.jar -d /tmp/dd-agent-unzipped

# Unzip antithesis-ffi jar
unzip -q antithesis-ffi-1.4.4.jar -d /tmp/antithesis-unzipped

# Copy com directory and all .so files from antithesis into dd-agent
cp -r /tmp/antithesis-unzipped/com /tmp/dd-agent-unzipped/
cp /tmp/antithesis-unzipped/libFfiWrapper.so /tmp/dd-agent-unzipped/

# Re-zip the modified dd-java-agent.jar
cd /tmp/dd-agent-unzipped && \
    zip -qr /dd-tracer/dd-java-agent.jar .

# Clean up temporary directories
rm -rf /tmp/dd-agent-unzipped /tmp/antithesis-unzipped antithesis-ffi-1.4.4.jar

echo "Installed Antithesis coverage instrumentation"