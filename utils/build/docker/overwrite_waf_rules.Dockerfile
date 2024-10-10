FROM system_tests/weblog

COPY ./binaries/waf_rule_set.json  /waf_rule_set.json
ENV DD_APPSEC_RULES=/waf_rule_set.json

# ruby lib use another name
ENV DD_APPSEC_RULESET=/waf_rule_set.json
