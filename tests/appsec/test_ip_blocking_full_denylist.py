# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


from utils import weblog, context, interfaces, rfc, bug, scenarios, missing_feature, features

from .utils import BaseFullDenyListTest


@rfc("https://docs.google.com/document/d/1GUd8p7HBp9gP0a6PZmDY26dpGrS1Ztef9OYdbK3Vq3M/edit")
@bug("nodejs@3.16.0" < context.library < "nodejs@3.18.0", reason="bugged on that version range")
@scenarios.appsec_blocking_full_denylist
@features.appsec_client_ip_blocking
class Test_AppSecIPBlockingFullDenylist(BaseFullDenyListTest):
    """A library should block requests from up to 2500 different blocked IP addresses."""

    def setup_blocked_ips(self):
        NOT_BLOCKED_IP = "42.42.42.3"

        self.setup_scenario()

        self.not_blocked_request = weblog.get(headers={"X-Forwarded-For": NOT_BLOCKED_IP})
        self.blocked_requests = [weblog.get(headers={"X-Forwarded-For": ip}) for ip in self.blocked_ips]

    @missing_feature(weblog_variant="spring-boot" and context.library < "java@0.111.0")
    @bug(
        context.library >= "java@1.22.0" and context.library < "java@1.35.0",
        reason="Failed on large expiration values, which are used in this test",
    )
    @missing_feature(library="python")
    def test_blocked_ips(self):
        """test blocked ips are enforced"""

        for r in self.blocked_requests:
            assert r.status_code == 403
            interfaces.library.assert_waf_attack(r, rule="blk-001-001")

        assert self.not_blocked_request.status_code == 200
        interfaces.library.assert_no_appsec_event(self.not_blocked_request)
