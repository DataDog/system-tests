# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


import pytest

from utils import context, weblog, interfaces, released, missing_feature, bug, coverage

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(golang={"gin": "1.37.0", "echo": "1.36.0", "chi": "1.36.0", "*": "1.34.0"})
@released(dotnet="1.28.6", java="0.87.0", nodejs="2.0.0", php_appsec="0.2.1", python="1.1.0rc2.dev")
@missing_feature(context.library == "ruby" and context.libddwaf_version is None)
@missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
@missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
@coverage.basic
class Test_Basic:
    """ Detect attacks on raw URI and headers with default rules """

    def setup_uri(self):
        self.r_uri = weblog.get("/waf/0x5c0x2e0x2e0x2f")

    def test_uri(self):
        """ Via server.request.uri.raw """
        # Note: we do not check the returned key_path nor rule_id for the alpha version
        interfaces.library.assert_waf_attack(self.r_uri, pattern="0x5c0x2e0x2e0x2f", address="server.request.uri.raw")

    def setup_headers(self):
        self.r_headers_1 = weblog.get("/waf/", headers={"MyHeader": "../../../secret.txt"})
        self.r_headers_2 = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    @bug(library="python@1.1.0", reason="a PR was not included in the release")
    def test_headers(self):
        """ Via server.request.headers.no_cookies """
        # Note: we do not check the returned key_path nor rule_id for the alpha version
        address = "server.request.headers.no_cookies"
        pattern = "/../" if context.appsec_rules_version < "1.2.6" else "../"
        interfaces.library.assert_waf_attack(self.r_headers_1, pattern=pattern, address=address)
        interfaces.library.assert_waf_attack(self.r_headers_2, pattern="Arachni/v", address=address)

    def setup_no_cookies(self):
        self.r_headers_1 = weblog.get("/waf/", headers={"MyHeader": "../../../secret.txt"})
        self.r_headers_2 = weblog.get("/waf/", cookies={"Cookie": "../../../secret.txt"})

    def test_no_cookies(self):
        """ Address server.request.headers.no_cookies should not include cookies. """
        # Relying on rule crs-930-110, test the following LFI attack is caught
        # on server.request.headers.no_cookies and then retry it with the cookies
        # to validate that cookies are properly excluded from server.request.headers.no_cookies.
        address = "server.request.headers.no_cookies"
        pattern = "/../" if context.appsec_rules_version < "1.2.6" else "../"
        interfaces.library.assert_waf_attack(self.r_headers_1, pattern=pattern, address=address)
        interfaces.library.assert_no_appsec_event(self.r_headers_2)
