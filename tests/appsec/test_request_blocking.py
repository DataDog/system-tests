# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features
from utils import interfaces
from utils import remote_config
from utils import scenarios
from utils import weblog


@features.envoy_external_processing
@features.haproxy_stream_processing_offload
@features.appsec_request_blocking
@scenarios.appsec_blocking_full_denylist
@scenarios.external_processing
@scenarios.stream_processing_offload
class Test_AppSecRequestBlocking:
    """A library should block requests when a rule is set to blocking mode."""

    def setup_request_blocking(self):
        rc_state = remote_config.rc_state
        rc_state.set_config(
            "datadog/2/ASM/ASM-base/config",
            {"rules_override": [{"on_match": ["block"], "rules_target": [{"tags": {"confidence": "1"}}]}]},
        )
        rc_state.set_config(
            "datadog/2/ASM/ASM-second/config",
            {"rules_override": [{"rules_target": [{"rule_id": "crs-913-110"}], "on_match": []}]},
        )
        self.config_state = rc_state.apply()

        self.blocked_requests1 = weblog.get(headers={"user-agent": "Arachni/v1"})
        self.blocked_requests2 = weblog.get(params={"random-key": "/netsparker-"})

    def test_request_blocking(self):
        """Test requests are blocked by rules in blocking mode"""

        assert self.config_state.state == remote_config.ApplyState.ACKNOWLEDGED

        assert self.blocked_requests1.status_code == 403
        interfaces.library.assert_waf_attack(self.blocked_requests1, rule="ua0-600-12x")

        assert self.blocked_requests2.status_code == 403
        interfaces.library.assert_waf_attack(self.blocked_requests2, rule="crs-913-120")
