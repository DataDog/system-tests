# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


import pytest

from utils import context, BaseTestCase, interfaces, released, irrelevant, missing_feature

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(golang="1.35.0" if context.weblog_variant == "echo" else "1.34.0-rc.4")
@released(dotnet="1.28.6", java="0.87.0")
@released(nodejs="2.0.0rc0", php_appsec="0.1.0", python="?")
@missing_feature(context.library == "ruby" and context.libddwaf_version is None)
class TestLFIAttempt(BaseTestCase):
    """
    Detect LFI attack attempts.
    """

    @irrelevant(
        context.library == "dotnet" and context.weblog_variant == "poc",
        reason="the .net framework is instrumented after the URI gets simplified",
    )
    @irrelevant(
        context.library == "php" and context.weblog_variant == "apache-mod",
        reason="apache resolves .. before passing it to mod_rewrite",
    )
    def test_uri(self):
        """
        Via server.request.uri.raw
        """
        # Note: we do not check the returned key_path nor rule_id for the alpha version
        r = self.weblog_get("/waf/../../../secret.txt")
        interfaces.library.assert_waf_attack(r, pattern="/../", address="server.request.uri.raw")

    def test_headers(self):
        """
        Via server.request.headers.no_cookies
        """
        # Note: we do not check the returned key_path nor rule_id for the alpha version
        r = self.weblog_get("/waf/", headers={"MyHeader": "../../../secret.txt"})
        interfaces.library.assert_waf_attack(r, pattern="/../", address="server.request.headers.no_cookies")


@released(golang="1.35.0" if context.weblog_variant == "echo" else "1.34.0-rc.4")
@released(dotnet="1.28.6", java="0.87.0", nodejs="2.0.0rc0", php_appsec="0.1.0", python="?")
@missing_feature(context.library == "ruby" and context.libddwaf_version is None)
class TestSecurityScanner(BaseTestCase):
    """
    Detect security scanners.
    """

    def test_headers(self):
        """
        Via the user-agent header in server.request.headers.no_cookies.
        """
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.assert_waf_attack(r, pattern="Arachni/v", address="server.request.headers.no_cookies")


@released(golang="1.35.0" if context.weblog_variant == "echo" else "1.34.0-rc.4")
@released(dotnet="1.28.6", java="0.87.0")
@released(nodejs="2.0.0rc0", php_appsec="0.1.0", python="?")
@missing_feature(context.library == "ruby" and context.libddwaf_version is None)
class TestAddresses(BaseTestCase):
    """
    Address server.request.headers.no_cookies should not include cookies.
    """

    def test_no_cookies(self):
        """
        Address server.request.headers.no_cookies should not include cookies.
        """
        # Relying on rule crs-930-110, test the following LFI attack is caught
        # on server.request.headers.no_cookies and then retry it with the cookies
        # to validate that cookies are properly excluded from server.request.headers.no_cookies.
        r = self.weblog_get("/waf/", headers={"MyHeader": "../../../secret.txt"})
        interfaces.library.assert_waf_attack(r, pattern="/../", address="server.request.headers.no_cookies")

        r = self.weblog_get("/waf/", cookies={"Cookie": "../../../secret.txt"})
        interfaces.library.assert_no_appsec_event(r)
