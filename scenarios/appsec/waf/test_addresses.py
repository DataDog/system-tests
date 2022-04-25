# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


from utils import context, BaseTestCase, interfaces, released, bug, irrelevant, missing_feature, flaky
import pytest


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(
    golang="1.37.0"
    if context.weblog_variant == "gin"
    else "1.36.0"
    if context.weblog_variant in ["echo", "chi"]
    else "1.34.0"
)
@released(nodejs="2.0.0", php_appsec="0.1.0", python="?")
class Test_Cookies(BaseTestCase):
    """Appsec supports server.request.cookies"""

    def test_cookies(self):
        """ Appsec WAF detects attackes in cookies """
        r = self.weblog_get("/waf/", cookies={"attack": ".htaccess"})
        interfaces.library.assert_waf_attack(r, pattern=".htaccess", address="server.request.cookies")

    @irrelevant(
        library="java",
        reason="cookies are not urldecoded; see RFC 6265, which only suggests they be base64 "
        "encoded to represent disallowed octets",
    )
    @irrelevant(library="golang", reason="Not handled by the Go standard cookie parser")
    def test_cookies_with_semicolon(self):
        """ Cookie with pattern containing a semicolon """
        r = self.weblog_get("/waf", cookies={"value": "%3Bshutdown--"})
        interfaces.library.assert_waf_attack(r, pattern=";shutdown--", address="server.request.cookies")

    @irrelevant(library="dotnet", reason="One space in the whole value cause kestrel to erase the whole value")
    def test_cookies_with_spaces(self):
        """ Cookie with pattern containing a space """
        r = self.weblog_get("/waf/", cookies={"x-attack": "var_dump ()"})
        interfaces.library.assert_waf_attack(r, pattern="var_dump ()", address="server.request.cookies")

    @irrelevant(library="golang", reason="Not handled by the Go standard cookie parser")
    @irrelevant(library="dotnet", reason="Quotation marks cause kestrel to erase the whole value")
    @bug(context.library < "java@0.96.0")
    def test_cookies_with_special_chars2(self):
        """Other cookies patterns"""
        r = self.weblog_get("/waf/", cookies={"x-attack": 'o:4:"x":5:{d}'})
        interfaces.library.assert_waf_attack(r, pattern='o:4:"x":5:{d}', address="server.request.cookies")
