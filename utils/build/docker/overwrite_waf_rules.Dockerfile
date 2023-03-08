FROM system_tests/weblog

COPY ./binaries/waf_rule_set.json  /waf_rule_set.json
ENV DD_APPSEC_RULES=/waf_rule_set.json

# ruby lib use another name
ENV DD_APPSEC_RULESET=/waf_rule_set.json

ARG SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
RUN echo $SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION