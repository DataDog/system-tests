# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import json

from utils import weblog, context, coverage, interfaces, released, bug, scenarios
from utils.tools import logger

with open("tests/appsec/rc_expected_requests_asm.json", encoding="utf-8") as f:
    EXPECTED_REQUESTS = json.load(f)


@released(dotnet="2.25.0", php_appsec="0.7.0", python="1.10.0", ruby="1.11.1", nodejs="3.19.0")
@released(
    java={
        "spring-boot": "1.9.0",
        "sprint-boot-jetty": "1.9.0",
        "spring-boot-undertow": "1.9.0",
        "spring-boot-openliberty": "1.9.0",
        "ratpack": "1.9.0",
        "jersey-grizzly2": "1.9.0",
        "resteasy-netty3": "1.9.0",
        "vertx3": "1.9.0",
        "*": "?",
    }
)
@released(golang="1.50.0-rc.1")
@coverage.basic
@scenarios.appsec_request_blocking
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

            state = data.get("request", {}).get("content", {}).get("client", {}).get("state", {})
            if len(state.get("config_states", [])) == 0 or state.get("has_error"):
                logger.info(f"rc request contains an error or no configs:\n{state}")
                return False

            for s in state["config_states"]:
                if s["id"] != "ASM-base" or s.get("apply_error") or s.get("apply_state", 0) != 2:
                    logger.info(f"rc request contains an error or wrong config:\n{state}")
                    return False

            return True

        interfaces.library.wait_for(remote_config_is_applied, timeout=30)

        self.blocked_requests1 = weblog.get(headers={"user-agent": "Arachni/v1"})
        self.blocked_requests2 = weblog.get(params={"random-key": "/netsparker-"})

    @bug(context.weblog_variant in ("rails50", "rails51", "rails52", "rails60"))
    def test_request_blocking(self):
        """test requests are blocked by rules in blocking mode"""

        assert self.blocked_requests1.status_code == 403
        interfaces.library.assert_waf_attack(self.blocked_requests1, rule="ua0-600-12x")

        assert self.blocked_requests2.status_code == 403
        interfaces.library.assert_waf_attack(self.blocked_requests2, rule="crs-913-120")
