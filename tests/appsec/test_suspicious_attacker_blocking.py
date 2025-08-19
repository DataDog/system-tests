# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


from utils import features
from utils import interfaces
from utils import remote_config as rc
from utils import weblog
from utils._context._scenarios.dynamic import dynamic_scenario


CONFIG_ENABLED = (
    "datadog/2/ASM_FEATURES/asm_features_activation/config",
    {"asm": {"enabled": True}},
)
BLOCK_405 = (
    "datadog/2/ASM/actions/config",
    {"actions": [{"id": "block_custom", "parameters": {"status_code": 405, "type": "auto"}, "type": "block_request"}]},
)

EXCLUSIONS = (
    "datadog/2/ASM/exclusions/config",
    {
        "exclusions": [
            {
                "id": "exc-000-001",
                "on_match": "block_custom",
                "conditions": [
                    {
                        "operator": "ip_match",
                        "parameters": {"data": "suspicious_ips_data_id", "inputs": [{"address": "http.client_ip"}]},
                    }
                ],
            }
        ]
    },
)

EXCLUSION_DATA = (
    "datadog/2/ASM_DATA/exclusions_data/config",
    {
        "exclusion_data": [
            {"id": "suspicious_ips_data_id", "type": "ip_with_expiration", "data": [{"value": "34.65.27.85"}]}
        ]
    },
)

BLOCK_416 = (
    "datadog/2/ASM/actions/config",
    {"actions": [{"id": "block_custom", "parameters": {"status_code": 416, "type": "auto"}, "type": "block_request"}]},
)

HEADERS_ATTACKER = {
    "User-Agent": "dd-test-scanner-log-block",
    "X-Real-Ip": "34.65.27.85",
}
HEADERS_REGULAR = {"User-Agent": "dd-test-scanner-log-block"}

HEADERS_ATTACKER_NON_BLOCKING = {
    "User-Agent": "Arachni/v1",
    "X-Real-Ip": "34.65.27.85",
}
HEADERS_REGULAR_NON_BLOCKING = {"User-Agent": "Arachni/v1"}


@dynamic_scenario(mandatory={"DD_APPSEC_WAF_TIMEOUT": "10000000", "DD_APPSEC_TRACE_RATE_LIMIT": "10000"})
@features.suspicious_attacker_blocking
class Test_Suspicious_Attacker_Blocking:
    """A library should block requests after AppSec is activated via remote config,
    using the blocking actions defined in the remote config.
    """

    def setup_block_suspicious_attacker(self):
        self.config_state_1 = rc.rc_state.reset().apply()
        self.response_1 = weblog.get("/waf/", headers=HEADERS_ATTACKER)

        self.config_state_2 = rc.rc_state.set_config(*CONFIG_ENABLED).apply()
        self.response_2 = weblog.get("/waf/", headers=HEADERS_ATTACKER)

        self.config_state_3 = (
            rc.rc_state.set_config(*BLOCK_405).set_config(*EXCLUSIONS).set_config(*EXCLUSION_DATA).apply()
        )
        self.response_3 = weblog.get("/waf/", headers=HEADERS_ATTACKER)
        self.response_3b = weblog.get("/waf/", headers=HEADERS_REGULAR)
        self.response_3ᐩ = weblog.get("/waf/", headers=HEADERS_ATTACKER_NON_BLOCKING)
        self.response_3bᐩ = weblog.get("/waf/", headers=HEADERS_REGULAR_NON_BLOCKING)

        self.config_state_4 = rc.rc_state.set_config(*BLOCK_416).apply()
        self.response_4 = weblog.get("/waf/", headers=HEADERS_ATTACKER)
        self.response_4b = weblog.get("/waf/", headers=HEADERS_REGULAR)
        self.response_4ᐩ = weblog.get("/waf/", headers=HEADERS_ATTACKER_NON_BLOCKING)
        self.response_4bᐩ = weblog.get("/waf/", headers=HEADERS_REGULAR_NON_BLOCKING)

        self.config_state_5 = rc.rc_state.del_config(EXCLUSION_DATA[0]).apply()
        self.response_5 = weblog.get("/waf/", headers=HEADERS_ATTACKER)
        self.response_5ᐩ = weblog.get("/waf/", headers=HEADERS_ATTACKER_NON_BLOCKING)

        self.config_state_6 = rc.rc_state.reset().apply()

    def test_block_suspicious_attacker(self):
        # ASM disabled
        assert self.config_state_1.state == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_no_appsec_event(self.response_1)
        assert self.response_1.status_code == 200

        # normal block
        assert self.config_state_2.state == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_waf_attack(self.response_2, rule="ua0-600-56x")
        assert self.response_2.status_code == 403

        # block on 405 if suspicious IP
        assert self.config_state_3.state == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_waf_attack(self.response_3, rule="ua0-600-56x")
        assert self.response_3.status_code == 405
        assert self.response_3b.status_code == 403
        # non blocking rule should block with suspicious IP
        assert self.response_3ᐩ.status_code == 405
        assert self.response_3bᐩ.status_code == 200

        # block on 416 if suspicious IP
        assert self.config_state_4.state == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_waf_attack(self.response_4, rule="ua0-600-56x")
        assert self.response_4.status_code == 416
        assert self.response_4b.status_code == 403
        # non blocking rule should block with suspicious IP
        assert self.response_4ᐩ.status_code == 416
        assert self.response_4bᐩ.status_code == 200

        # no more suspicious IP
        assert self.config_state_5.state == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_waf_attack(self.response_5, rule="ua0-600-56x")
        # non blocking rule should not block anymore
        assert self.response_5.status_code == 403
        assert self.response_5ᐩ.status_code == 200

        # properly reset all
        assert self.config_state_6.state == rc.ApplyState.ACKNOWLEDGED
