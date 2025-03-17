#!/bin/bash

set -eu

if [ "$#" -eq 0 ]; then
    EXTRA_ARGS=""
else
    EXTRA_ARGS="$1"
fi

# Look for custom dd-trace-api jar in custom binaries folder
CUSTOM_DD_TRACE_API_COUNT=$(find /binaries/dd-trace-api*.jar 2>/dev/null | wc -l)
if [ "$CUSTOM_DD_TRACE_API_COUNT" = 0 ]; then
    echo "Using default dd-trace-api"
elif [ "$CUSTOM_DD_TRACE_API_COUNT" = 1 ]; then
    CUSTOM_DD_TRACE_API=$(find /binaries/dd-trace-api*.jar)
    echo "Using custom dd-trace-api: ${CUSTOM_DD_TRACE_API}"
    mvn install:install-file -Dfile="$CUSTOM_DD_TRACE_API" -DgroupId=com.datadoghq -DartifactId=dd-trace-api -Dversion=9999 -Dpackaging=jar "$EXTRA_ARGS"
else
    echo "Too many dd-trace-api within binaries folder"
    exit 1
fi