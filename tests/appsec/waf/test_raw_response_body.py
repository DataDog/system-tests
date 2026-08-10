# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, scenarios, features, rfc


@rfc("https://docs.google.com/document/d/1gvYRWNQ28GyRIAepx59di-KxIqZsqY1a9XwFYaXmGG4")
@scenarios.appsec_custom_rules
@features.appsec_raw_response_body
class Test_RawResponseBody:
    """WAF detects attacks in raw HTTP response body (server.response.body.raw address)"""

    def setup_waf_detects_response_body(self):
        self.r = weblog.post(
            "/tag_value/payload_in_response_body_raw_attack/200",
            data={"attack": "server_response_body_raw_poison"},
        )

    def test_waf_detects_response_body(self):
        """WAF fires when the response body contains a known attack pattern"""
        assert self.r.status_code == 200
        interfaces.library.assert_waf_attack(self.r, address="server.response.body.raw")
