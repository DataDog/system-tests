FROM system_tests/weblog

ARG SYSTEM_TESTS_LIBRARY
ENV SYSTEM_TESTS_LIBRARY=$SYSTEM_TESTS_LIBRARY

ARG SYSTEM_TESTS_WEBLOG_VARIANT
ENV SYSTEM_TESTS_WEBLOG_VARIANT=$SYSTEM_TESTS_WEBLOG_VARIANT

# files for exotic scenarios
RUN echo "corrupted::data" > /appsec_corrupted_rules.yml
COPY tests/appsec/custom_rules.json /appsec_custom_rules.json
COPY tests/appsec/custom_rules_with_errors.json /appsec_custom_rules_with_errors.json
COPY tests/appsec/blocking_rule.json /appsec_blocking_rule.json
COPY tests/appsec/rasp/rasp_ruleset.json /appsec_rasp_ruleset.json

# for remote configuration tests
ENV DD_RC_TUF_ROOT='{"signed":{"_type":"root","spec_version":"1.0","version":1,"expires":"2032-05-29T12:49:41.030418-04:00","keys":{"ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e":{"keytype":"ed25519","scheme":"ed25519","keyid_hash_algorithms":["sha256","sha512"],"keyval":{"public":"7d3102e39abe71044d207550bda239c71380d013ec5a115f79f51622630054e6"}}},"roles":{"root":{"keyids":["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],"threshold":1},"snapshot":{"keyids":["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],"threshold":1},"targets":{"keyids":["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],"threshold":1},"timestsmp":{"keyids":["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],"threshold":1}},"consistent_snapshot":true},"signatures":[{"keyid":"ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e","sig":"d7e24828d1d3104e48911860a13dd6ad3f4f96d45a9ea28c4a0f04dbd3ca6c205ed406523c6c4cacfb7ebba68f7e122e42746d1c1a83ffa89c8bccb6f7af5e06"}]}'

COPY ./utils/build/docker/weblog-cmd.sh ./weblog-cmd.sh
RUN chmod +x app.sh
RUN chmod +x weblog-cmd.sh
CMD [ "./weblog-cmd.sh" ]
