# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import json

from tests.remote_config.test_remote_configuration import rc_check_request
from utils import weblog, context, coverage, interfaces, released, rfc, bug, irrelevant, scenarios
from utils.tools import logger

with open("tests/appsec/rc_expected_requests_block_ip_maxed_asm_data.json", encoding="utf-8") as f:
    EXPECTED_REQUESTS = json.load(f)


@rfc("https://docs.google.com/document/d/1GUd8p7HBp9gP0a6PZmDY26dpGrS1Ztef9OYdbK3Vq3M/edit")
@released(cpp="?", dotnet="2.16.0", php_appsec="0.7.0", python="?", ruby="?", nodejs="3.11", golang="1.47.0")
@released(
    java={
        "spring-boot": "0.110.0",
        "sprint-boot-jetty": "0.111.0",
        "spring-boot-undertow": "0.111.0",
        "spring-boot-openliberty": "0.115.0",
        "ratpack": "1.7.0",
        "jersey-grizzly2": "1.7.0",
        "resteasy-netty3": "1.7.0",
        "vertx3": "1.7.0",
        "*": "?",
    }
)
@irrelevant(
    context.appsec_rules_file is not None, reason="No Remote Config sub with custom rules file",
)
@bug(context.weblog_variant == "uds-echo")
@bug(context.library > "nodejs@3.16.0", reason="Under investigation")
@coverage.basic
@scenarios.appsec_ip_blocking_maxed
class Test_AppSecIPBlockingMaxed:
    """A library should block requests from up to 2500 different blocked IP addresses."""

    request_number = 0
    remote_config_is_sent = False

    @bug(context.library < "java@1.13.0", reason="id reported for config state is not the expected one")
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
        BLOCKED_IPS = [
            "245.159.180.146",
            "126.29.6.251",
            "59.9.47.235",
            "179.140.243.163",
            "136.26.224.167",
            "165.160.156.36",
            "172.2.59.155",
            "169.49.236.135",
        ]

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
                        if state["id"] == "ASM_DATA-third":
                            return True

            return False

        interfaces.library.wait_for(remote_config_asm_payload, timeout=30)
        interfaces.library.wait_for(remote_config_is_applied, timeout=30)

        self.not_blocked_request = weblog.get(headers={"X-Forwarded-For": NOT_BLOCKED_IP})
        self.blocked_requests = [weblog.get(headers={"X-Forwarded-For": ip}) for ip in BLOCKED_IPS]

    @released(
        java={
            "spring-boot": "0.111.0",
            "spring-boot-jetty": "0.111.0",
            "spring-boot-undertow": "0.111.0",
            "spring-boot-openliberty": "0.115.0",
            "ratpack": "1.7.0",
            "jersey-grizzly2": "1.7.0",
            "resteasy-netty3": "1.7.0",
            "vertx3": "1.7.0",
            "*": "?",
        }
    )
    def test_blocked_ips(self):
        """test blocked ips are enforced"""

        for r in self.blocked_requests:
            assert r.status_code == 403
            interfaces.library.assert_waf_attack(r, rule="blk-001-001")

        assert self.not_blocked_request.status_code == 200
        interfaces.library.assert_no_appsec_event(self.not_blocked_request)
