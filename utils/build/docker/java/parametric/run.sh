#!/bin/bash

DD_JAVA_AGENT=/client/tracer/dd-java-agent.jar

# Enable application debug level if tracer debug flag is enabled
case $(echo "${DD_TRACE_DEBUG:-false}" | tr '[:upper:]' '[:lower:]') in
  "true" | "1") export APM_TEST_CLIENT_LOG_LEVEL=debug;;
  *);;
esac

# Enable OTel Tracing API support for /trace/otel endpoint
ENABLE_OTEL_TRACING_API=-Ddd.trace.otel.enabled=true

# Enable crash tracking for /trace/crash related tests
ENABLE_CRASH_TRACKING=(-XX:OnError="/tmp/datadog/java/dd_crash_uploader.sh %p" \
  -XX:ErrorFile=/tmp/datadog/java/hs_err_pid_%p.log \
  -XX:OnOutOfMemoryError="/tmp/datadog/java/dd_oome_notifier.sh %p")

# Disable features
DISABLED_FEATURES=(-Ddd.telemetry.dependency-collection.enabled=false)

# Disable integrations to avoid creating unexpected spans
# - Spring Boot related integrations
# - AppSec process monitoring
DISABLE_INTEGRATIONS=(-Ddd.integration.servlet-request-body.enabled=false \
  -Ddd.integration.spring-beans.enabled=false \
  -Ddd.integration.spring-path-filter.enabled=false \
  -Ddd.integration.spring-web.enabled=false \
  -Ddd.integration.tomcat.enabled=false \
  -Ddd.integration.java-lang-appsec.enabled=false)

# Limit JIT to tier one as the client application is a short-lived process that frequently killed / restarted
OPTIMIZATION_OPTIONS=(-XX:TieredStopAtLevel=1)

# Start client application
# shellcheck disable=SC2086
java -Xmx128M -javaagent:"${DD_JAVA_AGENT}" \
  $ENABLE_OTEL_TRACING_API \
  "${ENABLE_CRASH_TRACKING[@]}" \
  "${DISABLED_FEATURES[@]}" \
  "${DISABLE_INTEGRATIONS[@]}" \
  "${OPTIMIZATION_OPTIONS[@]}" \
  ${SYSTEM_TESTS_EXTRA_COMMAND_ARGUMENTS:-} \
  -jar target/dd-trace-java-client-1.0.0.jar
