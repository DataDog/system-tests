#!/bin/bash

set -eu

BINARIES_DIR=$1 #/binaries

if [ $(ls $BINARIES_DIR/dd-java-agent*.jar | wc -l) = 0 ]; then
    BUILD_URL="https://github.com/DataDog/dd-trace-java/releases/latest/download/dd-java-agent.jar"
    echo "install from Github release: $BUILD_URL"
    # a loop, not curl's retry options: the images running it may have a curl too old for them
    for attempt in 1 2 3 4; do
        curl -Lf -o $BINARIES_DIR/dd-java-agent.jar $BUILD_URL && break
        [ $attempt = 4 ] && exit 1
        echo "Download failed, retrying in 5s"
        sleep 5
    done

elif [ $(ls $BINARIES_DIR/dd-java-agent*.jar | wc -l) = 1 ]; then
    echo "Install local file $(ls $BINARIES_DIR/dd-java-agent*.jar)"

else
    echo "Too many jar files in binaries"
    exit 1
fi

java -jar $BINARIES_DIR/dd-java-agent.jar > $BINARIES_DIR/SYSTEM_TESTS_LIBRARY_VERSION

echo "Installed $(cat $BINARIES_DIR/SYSTEM_TESTS_LIBRARY_VERSION) java library"