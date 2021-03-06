# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


import pytest

from utils import context, BaseTestCase, interfaces, released, missing_feature, bug, coverage

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(
    golang="1.37.0"
    if context.weblog_variant == "gin"
    else "1.36.0"
    if context.weblog_variant in ["echo", "chi"]
    else "1.34.0"
)
@released(dotnet="1.28.6", java="0.87.0", nodejs="2.0.0", php_appsec="0.2.1", python="1.1.0rc2.dev")
@missing_feature(context.library == "ruby" and context.libddwaf_version is None)
@coverage.basic
class Test_Basic(BaseTestCase):
    """
    Detect attacks on raw URI and headers with default rules
    """

    def test_uri(self):
        """
        Via server.request.uri.raw
        """
        # Note: we do not check the returned key_path nor rule_id for the alpha version
        r = self.weblog_get("/waf/0x5c0x2e0x2e0x2f")
        interfaces.library.assert_waf_attack(r, pattern="0x5c0x2e0x2e0x2f", address="server.request.uri.raw")

    @bug(library="python@1.1.0", reason="a PR was not included in the release")
    def test_headers(self):
        """
        Via server.request.headers.no_cookies
        """
        # Note: we do not check the returned key_path nor rule_id for the alpha version
        r = self.weblog_get("/waf/", headers={"MyHeader": "../../../secret.txt"})
        pattern = "/../" if context.appsec_rules_version < "1.2.6" else "../"
        interfaces.library.assert_waf_attack(r, pattern=pattern, address="server.request.headers.no_cookies")

        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.assert_waf_attack(r, pattern="Arachni/v", address="server.request.headers.no_cookies")

    def test_no_cookies(self):
        """
        Address server.request.headers.no_cookies should not include cookies.
        """
        # Relying on rule crs-930-110, test the following LFI attack is caught
        # on server.request.headers.no_cookies and then retry it with the cookies
        # to validate that cookies are properly excluded from server.request.headers.no_cookies.
        r = self.weblog_get("/waf/", headers={"MyHeader": "../../../secret.txt"})
        pattern = "/../" if context.appsec_rules_version < "1.2.6" else "../"
        interfaces.library.assert_waf_attack(r, pattern=pattern, address="server.request.headers.no_cookies")

        r = self.weblog_get("/waf/", cookies={"Cookie": "../../../secret.txt"})
        interfaces.library.assert_no_appsec_event(r)
