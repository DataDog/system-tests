#!/bin/bash

set -eu

if [ $(ls /binaries/opentelemetry-javaagent-r2dbc*.jar | wc -l) = 0 ]; then
    LIBRARY_URL='https://repo1.maven.org/maven2/io/opentelemetry/javaagent/instrumentation/opentelemetry-javaagent-r2dbc-1.0/2.5.0-alpha/opentelemetry-javaagent-r2dbc-1.0-2.5.0-alpha.jar'
    echo "install from Maven central: $LIBRARY_URL"
    curl  -Lf -o /dd-tracer/opentelemetry-javaagent-r2dbc.jar $LIBRARY_URL

elif [ $(ls /binaries/opentelemetry-javaagent-r2dbc*.jar | wc -l) = 1 ]; then
    echo "Install local file $(ls /binaries/opentelemetry-javaagent-r2dbc*.jar)"
    cp $(ls /binaries/opentelemetry-javaagent-r2dbc*.jar) /dd-tracer/opentelemetry-javaagent-r2dbc.jar

else
    echo "Too many jar files in binaries"
    exit 1
fi

echo "Installed OpenTelemetry drop-in library"
