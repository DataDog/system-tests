# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import json

from tests.remote_config.test_remote_configuration import rc_check_request
from utils import (
    weblog,
    context,
    coverage,
    interfaces,
    rfc,
    bug,
    scenarios,
    missing_feature,
    features,
)
from utils.tools import logger

with open("tests/appsec/rc_expected_requests_block_full_denylist_asm_data.json", encoding="utf-8",) as f:
    EXPECTED_REQUESTS = json.load(f)


@rfc("https://docs.google.com/document/d/1GUd8p7HBp9gP0a6PZmDY26dpGrS1Ztef9OYdbK3Vq3M/edit")
@bug(
    "nodejs@3.16.0" < context.library < "nodejs@3.18.0", reason="bugged on that version range",
)
@coverage.basic
@scenarios.appsec_blocking_full_denylist
@features.appsec_client_ip_blocking
class Test_AppSecIPBlockingFullDenylist:
    """A library should block requests from up to 2500 different blocked IP addresses."""

    request_number = 0
    python_request_number = 0

    @bug(
        context.library < "java@1.13.0", reason="id reported for config state is not the expected one",
    )
    def test_rc_protocol(self):
        """test sequence of remote config messages"""

        def validate(data):

            if self.request_number >= len(EXPECTED_REQUESTS):
                return True

            logger.info(f"validating rc request number {self.request_number}")
            rc_check_request(data, EXPECTED_REQUESTS[self.request_number], caching=True)
            self.python_request_number += 1
            if (
                context.library == "python"
                and str(context.library) < "python@1.14.0rc2"
                and context.weblog_variant != "uwsgi-poc"
            ):
                if self.python_request_number % 2 == 0:
                    self.request_number += 1
            else:
                self.request_number += 1

        interfaces.library.validate_remote_configuration(validator=validate)

    def setup_blocked_ips(self):
        NOT_BLOCKED_IP = "42.42.42.3"

        # Generate the list of 100 * 125 = 12500 blocked ips that are found in the rc_mocked_responses_asm_data_full_denylist.json
        # to edit or generate a new rc mocked response, use the DataDog/rc-tracer-client-test-generator repository
        BLOCKED_IPS = [f"12.8.{a}.{b}" for a in range(100) for b in range(125)]

        def remote_config_is_applied(data):
            if data["path"] == "/v0.7/config":
                if "config_states" in data.get("request", {}).get("content", {}).get("client", {}).get("state", {}):
                    config_states = data["request"]["content"]["client"]["state"]["config_states"]

                    for state in config_states:
                        if state["id"] == "ASM_DATA-third":
                            return True

            return False

        interfaces.library.wait_for_remote_config_request()
        interfaces.library.wait_for(remote_config_is_applied, timeout=30)

        self.not_blocked_request = weblog.get(headers={"X-Forwarded-For": NOT_BLOCKED_IP})
        self.blocked_requests = [
            weblog.get(headers={"X-Forwarded-For": BLOCKED_IPS[0]}),
            weblog.get(headers={"X-Forwarded-For": BLOCKED_IPS[2500]}),
            weblog.get(headers={"X-Forwarded-For": BLOCKED_IPS[-1]}),
        ]

    @missing_feature(weblog_variant="spring-boot" and context.library < "java@0.111.0")
    def test_blocked_ips(self):
        """test blocked ips are enforced"""

        for r in self.blocked_requests:
            assert r.status_code == 403
            interfaces.library.assert_waf_attack(r, rule="blk-001-001")

        assert self.not_blocked_request.status_code == 200
        interfaces.library.assert_no_appsec_event(self.not_blocked_request)
