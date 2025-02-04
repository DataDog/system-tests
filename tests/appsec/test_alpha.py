# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, weblog, interfaces, scenarios, bug, features


@features.threats_alpha_preview
@features.envoy_external_processing
@scenarios.external_processing
@scenarios.default
class Test_Basic:
    """Detect attacks on raw URI and headers with default rules"""

    def setup_uri(self):
        self.r_uri = weblog.get("/waf/0x5c0x2e0x2e0x2f")

    def test_uri(self):
        """Via server.request.uri.raw"""
        # Note: we do not check the returned key_path nor rule_id for the alpha version
        interfaces.library.assert_waf_attack(self.r_uri, pattern="0x5c0x2e0x2e0x2f", address="server.request.uri.raw")

    def setup_headers(self):
        self.r_headers_1 = weblog.get("/waf/", headers={"MyHeader": "../../../secret.txt"})
        self.r_headers_2 = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    @bug(context.library == "python@1.1.0", reason="APMRP-360")
    def test_headers(self):
        """Via server.request.headers.no_cookies"""
        # Note: we do not check the returned key_path nor rule_id for the alpha version
        address = "server.request.headers.no_cookies"
        pattern = "../"
        interfaces.library.assert_waf_attack(self.r_headers_1, pattern=pattern, address=address)
        interfaces.library.assert_waf_attack(self.r_headers_2, pattern="Arachni/v", address=address)

    def setup_no_cookies(self):
        self.r_headers_1 = weblog.get("/waf/", headers={"MyHeader": "../../../secret.txt"})
        self.r_headers_2 = weblog.get("/waf/", cookies={"Cookie": "../../../secret.txt"})

    def test_no_cookies(self):
        """Address server.request.headers.no_cookies should not include cookies."""
        # Relying on rule crs-930-110, test the following LFI attack is caught
        # on server.request.headers.no_cookies and then retry it with the cookies
        # to validate that cookies are properly excluded from server.request.headers.no_cookies.
        address = "server.request.headers.no_cookies"
        pattern = "../"
        interfaces.library.assert_waf_attack(self.r_headers_1, pattern=pattern, address=address)
        interfaces.library.assert_no_appsec_event(self.r_headers_2)
