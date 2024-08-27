#!/bin/bash

DD_JAVA_AGENT=/client/tracer/dd-java-agent.jar

# Enable application debug level if tracer debug flag is enabled
case $(echo "${DD_TRACE_DEBUG:-false}" | tr '[:upper:]' '[:lower:]') in
  "true" | "1") export APM_TEST_CLIENT_LOG_LEVEL=debug;;
  *);;
esac

# Run client library with:
# - OTel integration enabled to use the OTel API
# - Spring and its web-server integrations disabled to prevent generating unrelated spans
java -Xmx128M -javaagent:"${DD_JAVA_AGENT}" \
  -XX:TieredStopAtLevel=1 \
  -Ddd.jmxfetch.enabled=false \
  -Ddd.telemetry.dependency-collection.enabled=false \
  -Ddd.trace.otel.enabled=true \
  -Ddd.integration.servlet-request-body.enabled=false \
  -Ddd.integration.spring-beans.enabled=false \
  -Ddd.integration.spring-path-filter.enabled=false \
  -Ddd.integration.spring-web.enabled=false \
  -Ddd.integration.tomcat.enabled=false \
  -jar target/dd-trace-java-client-1.0.0.jar
