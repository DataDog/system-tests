#!/bin/sh
set -eu

trust_store=/tmp/system-tests-cacerts
cp "${JAVA_HOME}/lib/security/cacerts" "${trust_store}"
keytool -importcert -noprompt -trustcacerts \
  -alias system-tests-proxy \
  -file /app/system-tests-proxy-ca.cer \
  -keystore "${trust_store}" \
  -storepass changeit

JAVA_OPTS="${JAVA_OPTS:-} ${SYSTEM_TESTS_JAVA_PROXY_OPTS:-} -Djavax.net.ssl.trustStore=${trust_store} -Djavax.net.ssl.trustStorePassword=changeit"
export JAVA_OPTS

exec /app/system-tests-java-app.sh
