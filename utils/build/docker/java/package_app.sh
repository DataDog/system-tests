#!/bin/bash

set -eu

MAVEN_OPTS=

if [ -f /dd-tracer/dd-trace-api.jar ]; then
  MAVEN_OPTS="-DcustomDdTraceApi=/dd-tracer/dd-trace-api.jar"
fi

# shellcheck disable=SC2068
/usr/share/maven/bin/mvn "$MAVEN_OPTS" $@


