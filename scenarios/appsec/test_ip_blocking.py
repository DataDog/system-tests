# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import json

from scenarios.remote_config.test_remote_configuration import rc_check_request
from utils import BaseTestCase, context, coverage, interfaces, released, rfc, bug
from utils.tools import logger

with open("scenarios/appsec/rc_expected_requests_asm_data.json", encoding="utf-8") as f:
    EXPECTED_REQUESTS = json.load(f)


@rfc("https://docs.google.com/document/d/1GUd8p7HBp9gP0a6PZmDY26dpGrS1Ztef9OYdbK3Vq3M/edit")
@released(cpp="?", dotnet="2.16.0", java="0.110.0", php="?", python="?", ruby="?", nodejs="?", golang="?")
@coverage.basic
class Test_AppSecIPBlocking(BaseTestCase):
    """A library should block requests from blocked IP addresses."""

    request_number = 0

    def test_rc_protocol(self):
        """test sequence of remote config messages"""

        def validate(data):

            if self.request_number >= len(EXPECTED_REQUESTS):
                return True

            logger.info(f"validating rc request number {self.request_number}")
            rc_check_request(data, EXPECTED_REQUESTS[self.request_number], caching=True)
            self.request_number += 1

        interfaces.library.add_remote_configuration_validation(validator=validate)

    @bug(context.library == "java@0.110.0", reason="default action not implemented")
    def test_blocked_ips(self):
        """test blocked ips are enforced"""

        BLOCKED_IPS = ["42.42.42.1", "42.42.42.2"]
        NOT_BLOCKED_IPS = ["42.42.42.3"]

        def remote_config_is_sent(data):
            if data["path"] == "/v0.7/config":
                if "client_configs" in data.get("response", {}).get("content", {}):
                    return True

            return False

        # Probably a race condition here. We should wait for an explicit signal from the tracer
        # that the config has been applied. Otherwise, if applying the config take a while,
        # this test may be flacky
        interfaces.library.wait_for(remote_config_is_sent, timeout=30)

        for ip in BLOCKED_IPS:
            r = self.weblog_get(headers={"X-Forwarded-For": ip})
            interfaces.library.add_assertion(r.status_code == 403)
            interfaces.library.assert_waf_attack(r, rule="blk-001-001")

        for ip in NOT_BLOCKED_IPS:
            r = self.weblog_get(headers={"X-Forwarded-For": ip})
            interfaces.library.add_assertion(r.status_code == 200)
            interfaces.library.assert_no_appsec_event(r)
