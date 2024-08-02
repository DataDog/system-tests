#!/bin/bash

DD_JAVA_AGENT=/client/tracer/dd-java-agent.jar

# Enable application debug level if tracer debug flag is enabled
case $(echo "${DD_TRACE_DEBUG:-false}" | tr '[:upper:]' '[:lower:]') in
  "true" | "1") export APM_TEST_CLIENT_LOG_LEVEL=debug;;
  *);;
esac

java -Xmx128M -javaagent:"${DD_JAVA_AGENT}" \
  -XX:TieredStopAtLevel=1 \
  -Ddd.jmxfetch.enabled=false \
  -Ddd.telemetry.dependency-collection.enabled=false \
  -Ddd.integration.opentelemetry.experimental.enabled=true \
  -jar target/dd-trace-java-client-1.0.0.jar
