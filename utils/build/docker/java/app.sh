#!/bin/sh
set -eu
# shellcheck disable=SC2086

if [ "${INCLUDE_OTEL_DROP_IN:-}" = "true" ]; then
  JAVA_OPTS="${JAVA_OPTS:-} -Ddd.trace.otel.enabled=true -Dotel.javaagent.extensions=/app/opentelemetry-javaagent-r2dbc.jar"
fi

exec java -Xmx362m ${JAVA_OPTS:-} -javaagent:/app/dd-java-agent.jar -jar /app/app.jar ${APP_EXTRA_ARGS:-}