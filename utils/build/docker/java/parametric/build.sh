#!/bin/bash

MAVEN_PROFILES=

# Look for custom dd-trace-api jar in custom binaries folder
CUSTOM_DD_TRACE_API_COUNT=$(find /binaries/dd-trace-api*.jar 2>/dev/null | wc -l)
if [ "$CUSTOM_DD_TRACE_API_COUNT" = 0 ]; then
    echo "Using default dd-trace-api"
elif [ "$CUSTOM_DD_TRACE_API_COUNT" = 1 ]; then
    CUSTOM_DD_TRACE_API=$(find /binaries/dd-trace-api*.jar)
    echo "Using custom dd-trace-api: ${CUSTOM_DD_TRACE_API}"
    MAVEN_PROFILES="$MAVEN_PROFILES -DcustomDdTraceApi=${CUSTOM_DD_TRACE_API}"
else
    echo "Too many dd-trace-api within binaries folder"
    exit 1
fi

echo "Running Maven build with profiles ${MAVEN_PROFILES}"
mvn -q "${MAVEN_PROFILES}" -Dclient.protobuf.path=src/main/proto/ package
