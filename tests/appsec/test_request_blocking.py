# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import json

from utils import weblog, context, coverage, interfaces, released, rfc, bug, irrelevant, scenario
from utils.tools import logger

with open("tests/appsec/rc_expected_requests_asm.json", encoding="utf-8") as f:
    EXPECTED_REQUESTS = json.load(f)


@released(java="1.9.0")
@coverage.basic
@scenario("APPSEC_REQUEST_BLOCKING")
class Test_AppSecRequestBlocking:
    """A library should block requests when a rule is set to blocking mode."""

    request_number = 0

    def setup_request_blocking(self):
        def remote_config_is_applied(data):

            if data["path"] != "/v0.7/config":
                return False

            logger.info(f"waiting rc request number {self.request_number}")
            if self.request_number < len(EXPECTED_REQUESTS):
                self.request_number += 1
                return False

            # Make sure the tracer applied the configuration
            assert data["request"]["content"]["client"]["state"]["config_states"] == [
                {"apply_state": 2, "id": "datadog/2/ASM/ASM-base/config", "product": "ASM", "version": 1},
            ]
            assert not data["request"]["content"]["client"]["state"]["has_error"]
            return True

        interfaces.library.wait_for(remote_config_is_applied, timeout=30)

        self.blocked_requests = weblog.get(headers={"random-key": "acunetix-user-agreement"})

    def test_request_blocking(self):
        """test requests are blocked by rules in blocking mode"""

        assert self.blocked_requests.status_code == 403
        interfaces.library.assert_waf_attack(self.blocked_requests, rule="crs-913-110")
