FROM system_tests/weblog

RUN apt-get update

# Datadog setup
ENV DD_SERVICE=weblog
ENV DD_TRACE_HEADER_TAGS='user-agent:http.request.headers.user-agent'
ENV DD_TAGS='key1:val1, key2 : val2 '
ENV DD_PROFILING_ENABLED=true
ENV DD_ENV=system-tests
ENV DD_APPSEC_ENABLED=true
ENV DD_TRACE_DEBUG=true
ENV DD_TRACE_LOG_DIRECTORY=/var/log/system-tests

# 10 seconds
ENV DD_APPSEC_WAF_TIMEOUT=10000000  
ENV DD_APPSEC_TRACE_RATE_LIMIT=10000

ARG SYSTEM_TESTS_LIBRARY
ENV SYSTEM_TESTS_LIBRARY=$SYSTEM_TESTS_LIBRARY

ARG SYSTEM_TESTS_WEBLOG_VARIANT
ENV SYSTEM_TESTS_WEBLOG_VARIANT=$SYSTEM_TESTS_WEBLOG_VARIANT

ARG SYSTEM_TESTS_LIBRARY_VERSION
ENV SYSTEM_TESTS_LIBRARY_VERSION=$SYSTEM_TESTS_LIBRARY_VERSION

ARG SYSTEM_TESTS_PHP_APPSEC_VERSION
ENV SYSTEM_TESTS_PHP_APPSEC_VERSION=$SYSTEM_TESTS_PHP_APPSEC_VERSION

ARG SYSTEM_TESTS_LIBDDWAF_VERSION
ENV SYSTEM_TESTS_LIBDDWAF_VERSION=$SYSTEM_TESTS_LIBDDWAF_VERSION

ARG SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
ENV SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION=$SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

# Enable telemetry manually for now
ENV DD_INSTRUMENTATION_TELEMETRY_ENABLED=1

# Python specific setting to flush telemetry messages faster
ENV DD_INSTRUMENTATION_TELEMETRY_INTERVAL_SECONDS=10

# files for exotic scenarios
RUN echo "corrupted::data" > /appsec_corrupted_rules.yml
COPY scenarios/appsec/custom_rules.json /appsec_custom_rules.json
COPY scenarios/appsec/custom_rules_with_errors.json /appsec_custom_rules_with_errors.json

RUN apt-get install socat -y
COPY ./utils/build/docker/weblog-cmd.sh ./weblog-cmd.sh
RUN chmod +x app.sh
RUN chmod +x weblog-cmd.sh
CMD [ "./weblog-cmd.sh" ]
