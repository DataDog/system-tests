# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import re

from tests.appsec.utils import find_series
from utils import context
from utils import bug
from utils import features
from utils import interfaces
from utils import remote_config as rc
from utils import scenarios
from utils import weblog


CONFIG_ENABLED = (
    "datadog/2/ASM_FEATURES/asm_features_activation/config",
    {"asm": {"enabled": True}},
)
BLOCK_405 = (
    "datadog/2/ASM/actions/config",
    {"actions": [{"id": "block", "parameters": {"status_code": 405, "type": "json"}, "type": "block_request"}]},
)

BLOCK_505 = (
    "datadog/2/ASM/actions/config",
    {"actions": [{"id": "block", "parameters": {"status_code": 505, "type": "html"}, "type": "block_request"}]},
)

BLOCK_REDIRECT = (
    "datadog/2/ASM/actions/config",
    {
        "actions": [
            {
                "id": "block",
                "parameters": {"location": "http://google.com", "status_code": 302},
                "type": "redirect_request",
            }
        ]
    },
)


@scenarios.appsec_runtime_activation
@features.changing_rules_using_rc
class Test_BlockingActionChangesWithRemoteConfig:
    """A library should block requests after AppSec is activated via remote config,
    using the blocking actions defined in the remote config.
    """

    def setup_block_405(self):
        self.config_state_1 = rc.rc_state.reset().set_config(*CONFIG_ENABLED).apply()
        self.response_1 = weblog.get("/waf/", headers={"User-Agent": "dd-test-scanner-log-block"})

        self.config_state_2 = rc.rc_state.set_config(*BLOCK_405).apply()
        self.response_2 = weblog.get("/waf/", headers={"User-Agent": "dd-test-scanner-log-block"})

        self.config_state_3 = rc.rc_state.set_config(*BLOCK_505).apply()
        self.response_3 = weblog.get("/waf/", headers={"User-Agent": "dd-test-scanner-log-block"})

        self.config_state_4 = rc.rc_state.set_config(*BLOCK_REDIRECT).apply()
        self.response_4 = weblog.get(
            "/waf/", headers={"User-Agent": "dd-test-scanner-log-block"}, allow_redirects=False
        )

        self.config_state_5 = rc.rc_state.reset().apply()
        self.response_5 = weblog.get("/waf/", headers={"User-Agent": "dd-test-scanner-log-block"})

    def test_block_405(self):
        # normal block
        assert self.config_state_1.state == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_waf_attack(self.response_1, rule="ua0-600-56x")
        assert self.response_1.status_code == 403

        # block on 405/json with RC
        assert self.config_state_2.state == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_waf_attack(self.response_2, rule="ua0-600-56x")
        assert self.response_2.status_code == 405
        # assert self.response_2.headers["content-type"] == "application/json"

        # block on 505/html with RC
        assert self.config_state_3.state == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_waf_attack(self.response_3, rule="ua0-600-56x")
        assert self.response_3.status_code == 505
        assert self.response_3.headers["content-type"].startswith("text/html")

        # block on 505/html with RC
        assert self.config_state_4.state == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_waf_attack(self.response_4, rule="ua0-600-56x")
        assert self.response_4.status_code == 302
        assert self.response_4.text == "" or '<a href="http://google.com">' in self.response_4.text
        assert self.response_4.headers["location"] == "http://google.com"

        # ASM disabled
        assert self.config_state_5.state == rc.ApplyState.ACKNOWLEDGED
        assert self.response_5.status_code == 200
        interfaces.library.assert_no_appsec_event(self.response_5)


RULE_FILE: tuple[str, dict] = (
    "datadog/2/ASM_DD/rules/config",
    {
        "version": "2.2",
        "metadata": {"rules_version": "2.71.8182"},
        "rules": [
            {
                "id": "ua0-600-12x",
                "name": "Arachni",
                "tags": {
                    "type": "attack_tool",
                    "category": "attack_attempt",
                    "cwe": "200",
                    "capec": "1000/118/169",
                    "tool_name": "Arachni",
                    "confidence": "1",
                },
                "conditions": [
                    {
                        "parameters": {
                            "inputs": [{"address": "server.request.headers.no_cookies", "key_path": ["user-agent"]}],
                            "regex": "^Arachni\\/v",
                        },
                        "operator": "match_regex",
                    }
                ],
                "transformers": [],
            },
        ],
    },
)


@scenarios.appsec_runtime_activation
@features.changing_rules_using_rc
class Test_UpdateRuleFileWithRemoteConfig:
    """A library should use the default rules when AppSec is activated via remote config,
    and no rule file is provided by ASM_DD. It should also revert to the default rules
    when the remote config rule file is deleted.
    Also test the span tags and telemetry data for the rule version.
    """

    def setup_update_rules(self):
        self.config_state_1 = rc.rc_state.reset().set_config(*CONFIG_ENABLED).apply()
        self.response_1 = weblog.get("/waf/", headers={"User-Agent": "dd-test-scanner-log-block"})
        self.response_1b = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

        self.config_state_2 = rc.rc_state.set_config(*RULE_FILE).apply()
        self.response_2 = weblog.get("/waf/", headers={"User-Agent": "dd-test-scanner-log-block"})
        self.response_2b = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

        self.config_state_3 = rc.rc_state.set_config(*BLOCK_405).apply()
        self.response_3 = weblog.get("/waf/", headers={"User-Agent": "dd-test-scanner-log-block"})
        self.response_3b = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

        self.config_state_4 = rc.rc_state.del_config(RULE_FILE[0]).apply()
        self.response_4 = weblog.get("/waf/", headers={"User-Agent": "dd-test-scanner-log-block"})
        self.response_4b = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

        self.config_state_5 = rc.rc_state.reset().apply()

    @bug(
        context.library < "nodejs@5.25.0", reason="APMRP-360"
    )  # rules version was not correctly reported after an RC update
    def test_update_rules(self):
        expected_rules_version_tag = "_dd.appsec.event_rules.version"
        expected_version_regex = r"[0-9]+\.[0-9]+\.[0-9]+"

        def validate_waf_rule_version_tag(span, appsec_data):  # noqa: ARG001
            """Validate the mandatory event_rules.version tag is added to the request span having an attack"""
            meta = span["meta"]
            assert expected_rules_version_tag in meta, f"missing span meta tag `{expected_rules_version_tag}` in meta"
            assert re.match(expected_version_regex, meta[expected_rules_version_tag])
            return True

        def validate_waf_rule_version_tag_by_rc(span, appsec_data):  # noqa: ARG001
            """Validate the mandatory event_rules.version tag is added to the request span having an attack with expected rc version"""
            meta: dict = span["meta"]
            assert expected_rules_version_tag in meta, f"missing span meta tag `{expected_rules_version_tag}` in meta"
            assert meta[expected_rules_version_tag] == RULE_FILE[1]["metadata"]["rules_version"]
            return True

        # normal block
        assert self.config_state_1.state == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_waf_attack(self.response_1, rule="ua0-600-56x")
        assert self.response_1.status_code == 403
        interfaces.library.validate_appsec(self.response_1, validate_waf_rule_version_tag)
        interfaces.library.assert_waf_attack(self.response_1b, rule="ua0-600-12x")
        assert self.response_1b.status_code == 200
        interfaces.library.validate_appsec(self.response_1b, validate_waf_rule_version_tag)

        # new rule file with only 12x
        assert self.config_state_2.state == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_no_appsec_event(self.response_2)
        assert self.response_2.status_code == 200
        interfaces.library.assert_no_appsec_event(self.response_2)
        interfaces.library.assert_waf_attack(self.response_2b, rule="ua0-600-12x")
        assert self.response_2b.status_code == 200
        interfaces.library.validate_appsec(self.response_2b, validate_waf_rule_version_tag_by_rc)

        # block on 405/json with RC. It must not change anything for the new rule file
        assert self.config_state_3.state == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_no_appsec_event(self.response_3)
        assert self.response_3.status_code == 200
        interfaces.library.assert_no_appsec_event(self.response_3)
        interfaces.library.assert_waf_attack(self.response_3b, rule="ua0-600-12x")
        assert self.response_3b.status_code == 200
        interfaces.library.validate_appsec(self.response_3b, validate_waf_rule_version_tag_by_rc)

        # Switch back to default rules but keep updated blocking action
        assert self.config_state_4.state == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_waf_attack(self.response_4, rule="ua0-600-56x")
        interfaces.library.validate_appsec(self.response_4, validate_waf_rule_version_tag)
        assert self.response_4.status_code == 405
        interfaces.library.assert_waf_attack(self.response_4b, rule="ua0-600-12x")
        assert self.response_4b.status_code == 200
        interfaces.library.validate_appsec(self.response_4b, validate_waf_rule_version_tag)

        # ASM disabled
        assert self.config_state_5.state == rc.ApplyState.ACKNOWLEDGED

        # Check for rule version in telemetry
        series = find_series("generate-metrics", "appsec", ["waf.requests", "waf.init", "waf.requests"])
        rule_versions = set()
        for s in series:
            for t in s.get("tags", ()):
                if t.startswith("event_rules_version:"):
                    rule_versions.add(t[20:].strip())
        # depending of previous tests, we should have at least the current RC version and the static file version.
        assert len(rule_versions) >= 2
        assert RULE_FILE[1]["metadata"]["rules_version"] in rule_versions
        for r in rule_versions:
            assert re.match(expected_version_regex, r), f"version [{r}] doesn't match expected version regex"
