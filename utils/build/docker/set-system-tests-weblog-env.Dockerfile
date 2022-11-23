FROM system_tests/weblog

RUN apt-get update

# Datadog setup
ENV DD_SERVICE=weblog
ENV DD_VERSION=1.0.0
ENV DD_TAGS='key1:val1, key2 : val2 '
ENV DD_PROFILING_ENABLED=true
ENV DD_ENV=system-tests
ENV DD_TRACE_DEBUG=true
ENV DD_TRACE_LOG_DIRECTORY=/var/log/system-tests
ENV DD_TRACE_COMPUTE_STATS=true

# 10 seconds
ENV DD_APPSEC_WAF_TIMEOUT=10000000
ENV DD_APPSEC_TRACE_RATE_LIMIT=10000

ENV DD_IAST_ENABLED=true
ENV DD_IAST_REQUEST_SAMPLING=100

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

# Flush telemetry messages faster
ENV DD_HEARTBEAT_TELEMETRY_INTERVAL=5

# files for exotic scenarios
RUN echo "corrupted::data" > /appsec_corrupted_rules.yml
COPY tests/appsec/custom_rules.json /appsec_custom_rules.json
COPY tests/appsec/custom_rules_with_errors.json /appsec_custom_rules_with_errors.json

# for remote configuration tests
ENV DD_RC_TUF_ROOT='{"signed":{"_type":"root","spec_version":"1.0","version":1,"expires":"2032-05-29T12:49:41.030418-04:00","keys":{"ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e":{"keytype":"ed25519","scheme":"ed25519","keyid_hash_algorithms":["sha256","sha512"],"keyval":{"public":"7d3102e39abe71044d207550bda239c71380d013ec5a115f79f51622630054e6"}}},"roles":{"root":{"keyids":["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],"threshold":1},"snapshot":{"keyids":["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],"threshold":1},"targets":{"keyids":["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],"threshold":1},"timestsmp":{"keyids":["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],"threshold":1}},"consistent_snapshot":true},"signatures":[{"keyid":"ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e","sig":"d7e24828d1d3104e48911860a13dd6ad3f4f96d45a9ea28c4a0f04dbd3ca6c205ed406523c6c4cacfb7ebba68f7e122e42746d1c1a83ffa89c8bccb6f7af5e06"}]}'

RUN apt-get install socat -y
COPY ./utils/build/docker/weblog-cmd.sh ./weblog-cmd.sh
RUN chmod +x app.sh
RUN chmod +x weblog-cmd.sh
CMD [ "./weblog-cmd.sh" ]
