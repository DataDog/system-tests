#!/bin/bash

set -eu

BINARIES_DIR=$1 #/binaries

if [ $(ls $BINARIES_DIR/dd-java-agent*.jar | wc -l) = 0 ]; then
    BUILD_URL="https://github.com/DataDog/dd-trace-java/releases/latest/download/dd-java-agent.jar"
    echo "install from Github release: $BUILD_URL"
    curl  -Lf -o $BINARIES_DIR/dd-java-agent.jar $BUILD_URL

elif [ $(ls $BINARIES_DIR/dd-java-agent*.jar | wc -l) = 1 ]; then
    echo "Install local file $(ls $BINARIES_DIR/dd-java-agent*.jar)"

else
    echo "Too many jar files in binaries"
    exit 1
fi

java -jar $BINARIES_DIR/dd-java-agent.jar > $BINARIES_DIR/SYSTEM_TESTS_LIBRARY_VERSION

echo "Installed $(cat $BINARIES_DIR/SYSTEM_TESTS_LIBRARY_VERSION) java library"

#Install Antithesis coverage instrumentation
RUN mkdir -p /opt/antithesis/catalog
RUN ln -s $BINARIES_DIR /opt/antithesis/catalog/app
RUN wget https://repo1.maven.org/maven2/com/antithesis/ffi/1.4.4/ffi-1.4.4.jar -O antithesis-ffi-1.4.4.jar

# Unzip dd-java-agent.jar
RUN unzip -q $BINARIES_DIR/dd-java-agent.jar -d /tmp/dd-agent-unzipped

# Unzip antithesis-ffi jar
RUN unzip -q antithesis-ffi-1.4.4.jar -d /tmp/antithesis-unzipped

# Copy com directory and all .so files from antithesis into dd-agent
RUN cp -r /tmp/antithesis-unzipped/com /tmp/dd-agent-unzipped/
RUN cp /tmp/antithesis-unzipped/libFfiWrapper.so /tmp/dd-agent-unzipped/

# Re-zip the modified dd-java-agent.jar
RUN cd /tmp/dd-agent-unzipped && \
    zip -qr $BINARIES_DIR/dd-java-agent.jar .

# Clean up temporary directories
RUN rm -rf /tmp/dd-agent-unzipped /tmp/antithesis-unzipped antithesis-ffi-1.4.4.jar

echo "Installed Antithesis coverage instrumentation"
