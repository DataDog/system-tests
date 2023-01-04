# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import json

from tests.remote_config.test_remote_configuration import rc_check_request
from utils import weblog, context, coverage, interfaces, released, rfc, bug, irrelevant, scenario
from utils.tools import logger

with open("tests/appsec/rc_expected_requests_asm_data.json", encoding="utf-8") as f:
    EXPECTED_REQUESTS = json.load(f)


@rfc("https://docs.google.com/document/d/1GUd8p7HBp9gP0a6PZmDY26dpGrS1Ztef9OYdbK3Vq3M/edit")
@released(cpp="?", dotnet="2.16.0", php="?", python="?", ruby="?", nodejs="?", golang="?")
@released(
    java={
        "spring-boot": "0.110.0",
        "sprint-boot-jetty": "0.111.0",
        "spring-boot-undertow": "0.111.0",
        "spring-boot-openliberty": "0.115.0",
        "*": "?",
    }
)
@irrelevant(context.appsec_rules_file == "")
@bug(context.weblog_variant == "spring-boot-undertow" and context.appsec_rules_version == "1.4.2")
@coverage.basic
@scenario("APPSEC_IP_BLOCKING")
class Test_AppSecIPBlocking:
    """A library should block requests from blocked IP addresses."""

    request_number = 0
    remote_config_is_sent = False

    @bug(context.library >= "java@1.1.0" and context.weblog_variant == "spring-boot-openliberty")
    @bug(context.library >= "java@1.1.0" and context.weblog_variant == "spring-boot")
    def test_rc_protocol(self):
        """test sequence of remote config messages"""

        def validate(data):

            if self.request_number >= len(EXPECTED_REQUESTS):
                return True

            logger.info(f"validating rc request number {self.request_number}")
            rc_check_request(data, EXPECTED_REQUESTS[self.request_number], caching=True)
            self.request_number += 1

        interfaces.library.validate_remote_configuration(validator=validate)

    def setup_blocked_ips(self):
        NOT_BLOCKED_IP = "42.42.42.3"
        BLOCKED_IPS = ["42.42.42.1", "42.42.42.2"]

        def remote_config_asm_payload(data):
            if data["path"] == "/v0.7/config":
                if "client_configs" in data.get("response", {}).get("content", {}):
                    self.remote_config_is_sent = True
                    return True

            return False

        def remote_config_is_applied(data):
            if data["path"] == "/v0.7/config" and self.remote_config_is_sent:
                if "config_states" in data.get("request", {}).get("content", {}).get("client", {}).get("state", {}):
                    config_states = data["request"]["content"]["client"]["state"]["config_states"]

                    for state in config_states:
                        if state["id"] == "ASM_DATA-base":
                            return True

            return False

        interfaces.library.wait_for(remote_config_asm_payload, timeout=30)
        interfaces.library.wait_for(remote_config_is_applied, timeout=30)

        self.not_blocked_request = weblog.get(headers={"X-Forwarded-For": NOT_BLOCKED_IP})
        self.blocked_requests = [weblog.get(headers={"X-Forwarded-For": ip}) for ip in BLOCKED_IPS]

    @bug(context.library == "java@0.110.0", reason="default action not implemented")
    @bug(context.library <= "java@0.114.0" and context.weblog_variant == "spring-boot-openliberty")
    @bug(context.library >= "java@1.1.0" and context.weblog_variant == "spring-boot-openliberty")
    @bug(context.library >= "java@1.1.0" and context.weblog_variant == "spring-boot")
    def test_blocked_ips(self):
        """test blocked ips are enforced"""

        for r in self.blocked_requests:
            assert r.status_code == 403
            interfaces.library.assert_waf_attack(r, rule="blk-001-001")

        assert self.not_blocked_request.status_code == 200
        interfaces.library.assert_no_appsec_event(self.not_blocked_request)
