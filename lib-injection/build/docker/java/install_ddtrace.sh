#!/bin/bash

set -eu

BINARIES_DIR=$1 #/binaries

if [ $(ls $BINARIES_DIR/dd-java-agent*.jar | wc -l) = 0 ]; then
    BUILD_URL="https://github.com/DataDog/dd-trace-java/releases/latest/download/dd-java-agent.jar"
    echo "install from Github release: $BUILD_URL"
    curl -Lf -o $BINARIES_DIR/dd-java-agent.jar $BUILD_URL

elif [ $(ls $BINARIES_DIR/dd-java-agent*.jar | wc -l) = 1 ]; then
    echo "Install local file $(ls $BINARIES_DIR/dd-java-agent*.jar)"

else
    echo "Too many jar files in binaries"
    exit 1
fi

java -jar $BINARIES_DIR/dd-java-agent.jar >$BINARIES_DIR/SYSTEM_TESTS_LIBRARY_VERSION

echo "Installed $(cat $BINARIES_DIR/SYSTEM_TESTS_LIBRARY_VERSION) java library"
