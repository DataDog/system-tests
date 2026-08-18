#!/bin/sh
set -eu

trust_store=/tmp/system-tests-cacerts
cp "${JAVA_HOME}/lib/security/cacerts" "${trust_store}"
keytool -importcert -noprompt -trustcacerts \
  -alias system-tests-proxy \
  -file /app/system-tests-proxy-ca.cer \
  -keystore "${trust_store}" \
  -storepass changeit

JAVA_OPTS="${JAVA_OPTS:-} -Djavax.net.ssl.trustStore=${trust_store} -Djavax.net.ssl.trustStorePassword=changeit"

if [ "${INCLUDE_OTEL_DROP_IN:-}" = "true" ]; then
  JAVA_OPTS="${JAVA_OPTS} -Ddd.trace.otel.enabled=true -Dotel.javaagent.extensions=/app/opentelemetry-javaagent-r2dbc.jar"
fi

# shellcheck disable=SC2086
exec java -Xmx362m ${JAVA_OPTS} -javaagent:/app/dd-java-agent.jar -jar /app/app.jar ${APP_EXTRA_ARGS:-}
