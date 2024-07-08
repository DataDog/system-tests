# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, scenarios, features, remote_config


@scenarios.appsec_request_blocking
@features.appsec_request_blocking
class Test_AppSecRequestBlocking:
    """A library should block requests when a rule is set to blocking mode."""

    def setup_request_blocking(self):
        command = remote_config.RemoteConfigCommand(version=0)
        command.add_client_config(
            "datadog/2/ASM/ASM-base/config",
            {"rules_override": [{"on_match": ["block"], "rules_target": [{"tags": {"confidence": "1"}}]}]},
        )
        command.add_client_config(
            "datadog/2/ASM/ASM-second/config",
            {"rules_override": [{"rules_target": [{"rule_id": "crs-913-110"}], "on_match": []}]},
        )
        self.first_states = command.send()

        command.add_client_config("datadog/2/ASM/ASM-base/config", None)
        self.second_states = command.send()

        self.blocked_requests1 = weblog.get(headers={"user-agent": "Arachni/v1"})
        self.blocked_requests2 = weblog.get(params={"random-key": "/netsparker-"})

    def test_request_blocking(self):
        """test requests are blocked by rules in blocking mode"""

        assert self.blocked_requests1.status_code == 403
        interfaces.library.assert_waf_attack(self.blocked_requests1, rule="ua0-600-12x")

        assert self.blocked_requests2.status_code == 403
        interfaces.library.assert_waf_attack(self.blocked_requests2, rule="crs-913-120")
