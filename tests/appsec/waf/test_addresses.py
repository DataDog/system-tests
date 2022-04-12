# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


from utils import context, BaseTestCase, interfaces, released, bug, irrelevant, missing_feature, flaky
import pytest


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


# WAF/current ruleset don't support looking at keys at all
@released(golang="?", dotnet="?", java="?", nodejs="?", php="?", python="?", ruby="1.0.0.beta1")
class Test_UrlQueryKey(BaseTestCase):
    """Appsec supports keys on server.request.query"""

    def test_query_key(self):
        """ AppSec catches attacks in URL query key"""
        r = self.weblog_get("/waf/", params={"appscan_fingerprint": "attack"})
        interfaces.library.assert_waf_attack(r, pattern="appscan_fingerprint", address="server.request.query")

    @missing_feature(library="ruby")
    def test_query_key_encoded(self):
        """ AppSec catches attacks in URL query encoded key"""
        r = self.weblog_get("/waf/", params={"<script>": "attack"})
        interfaces.library.assert_waf_attack(r, pattern="<script>", address="server.request.query")


@released(golang="1.35.0")
@released(dotnet="1.28.6", java="0.87.0", nodejs="2.0.0", php_appsec="0.1.0", python="?", ruby="0.54.2")
@missing_feature(context.library <= "golang@1.36.2" and context.weblog_variant == "gin")
class Test_UrlQuery(BaseTestCase):
    """Appsec supports values on server.request.query"""

    def test_query_argument(self):
        """ AppSec catches attacks in URL query value"""
        r = self.weblog_get("/waf/", params={"attack": "appscan_fingerprint"})
        interfaces.library.assert_waf_attack(r, pattern="appscan_fingerprint", address="server.request.query")

    def test_query_encoded(self):
        """ AppSec catches attacks in URL query value, even encoded"""
        r = self.weblog_get("/waf/", params={"key": "<script>"})
        interfaces.library.assert_waf_attack(r, address="server.request.query")

    @irrelevant(context.agent_version >= "1.2.6", reason="Need to find another rule")
    def test_query_with_strict_regex(self):
        """ AppSec catches attacks in URL query value, even with regex containing start and end char"""
        r = self.weblog_get("/waf/", params={"value": "0000012345"})
        interfaces.library.assert_waf_attack(r, pattern="0000012345", address="server.request.query")


@released(golang="1.36.0" if context.weblog_variant in ["echo", "chi"] else "1.34.0")
@released(dotnet="1.28.6", java="0.87.0")
@released(nodejs="2.0.0", php_appsec="0.1.0", python="0.58.5")
@flaky(context.library <= "php@0.68.2")
@missing_feature(context.library <= "golang@1.36.2" and context.weblog_variant == "gin")
class Test_UrlRaw(BaseTestCase):
    """Appsec supports server.request.uri.raw"""

    def test_path(self):
        """ AppSec catches attacks in raw URL path"""
        r = self.weblog_get("/waf/0x5c0x2e0x2e0x2f")
        interfaces.library.assert_waf_attack(r, pattern="0x5c0x2e0x2e0x2f", address="server.request.uri.raw")


@released(golang="1.36.0" if context.weblog_variant in ["echo", "chi"] else "1.34.0")
@released(dotnet="1.28.6", java="0.87.0")
@released(nodejs="2.0.0", php_appsec="0.1.0")
@flaky(context.library <= "php@0.68.2")
@missing_feature(context.library <= "golang@1.36.2" and context.weblog_variant == "gin")
@missing_feature(context.library < "python@0.58.5")
class Test_Headers(BaseTestCase):
    """Appsec supports server.request.headers.no_cookies"""

    @missing_feature(library="python")
    def test_value(self):
        """ Appsec WAF detects attacks in header value """
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.assert_waf_attack(
            r, pattern="Arachni/v", address="server.request.headers.no_cookies", key_path=["user-agent"]
        )

    @missing_feature(library="python")
    def test_specific_key(self):
        """ Appsec WAF detects attacks on specific header x-file-name or referer, and report it """
        r = self.weblog_get("/waf/", headers={"x-file-name": "routing.yml"})
        interfaces.library.assert_waf_attack(
            r, pattern="routing.yml", address="server.request.headers.no_cookies", key_path=["x-file-name"]
        )

        r = self.weblog_get("/waf/", headers={"X-File-Name": "routing.yml"})
        interfaces.library.assert_waf_attack(
            r, pattern="routing.yml", address="server.request.headers.no_cookies", key_path=["x-file-name"]
        )

        r = self.weblog_get("/waf/", headers={"X-Filename": "routing.yml"})
        interfaces.library.assert_waf_attack(
            r, pattern="routing.yml", address="server.request.headers.no_cookies", key_path=["x-filename"]
        )

    @missing_feature(library="python")
    @irrelevant(library="ruby", reason="Rack transforms underscores into dashes")
    @irrelevant(library="php", reason="PHP normalizes into dashes; additionally, matching on keys is not supported")
    def test_specific_key2(self):
        """ attacks on specific header X_Filename, and report it """
        r = self.weblog_get("/waf/", headers={"X_Filename": "routing.yml"})
        interfaces.library.assert_waf_attack(
            r, pattern="routing.yml", address="server.request.headers.no_cookies", key_path=["x_filename"]
        )

    @missing_feature(library="python")
    @missing_feature(context.library < "golang@1.36.0" and context.weblog_variant == "echo")
    def test_specific_key3(self):
        """ When a specific header key is specified, other key are ignored """
        r = self.weblog_get("/waf/", headers={"referer": "<script >"})
        interfaces.library.assert_waf_attack(r, address="server.request.headers.no_cookies", key_path=["referer"])

        r = self.weblog_get("/waf/", headers={"RefErEr": "<script >"})
        interfaces.library.assert_waf_attack(r, address="server.request.headers.no_cookies", key_path=["referer"])

    def test_specific_wrong_key(self):
        """ When a specific header key is specified in rules, other key are ignored """
        r = self.weblog_get("/waf/", headers={"xfilename": "routing.yml"})
        interfaces.library.assert_no_appsec_event(r)

        r = self.weblog_get("/waf/", headers={"not-referer": "<script >"})
        interfaces.library.assert_no_appsec_event(r)


@irrelevant(context.appsec_rules_version >= "1.2.7", reason="cookies were disabled for the time being")
@released(
    golang="1.37.0"
    if context.weblog_variant == "gin"
    else "1.36.0"
    if context.weblog_variant in ["echo", "chi"]
    else "1.34.0"
)
@released(nodejs="2.0.0", php_appsec="0.1.0", python="?")
class Test_Cookies_ToBeRestoredOnceWeHaveRules(BaseTestCase):
    """Appsec supports server.request.cookies, legacy test"""

    # Cookies rules has been removed in rules version 1.2.7. Test on cookies are now done on custom rules scenario.
    # Once we have rules with cookie back in the default rules set, we can re-use this class to validated this feature

    def test_cookies(self):
        """ Appsec WAF detects attackes in cookies """
        r = self.weblog_get("/waf/", cookies={"attack": ".htaccess"})
        interfaces.library.assert_waf_attack(r, pattern=".htaccess", address="server.request.cookies")

    @missing_feature(library="java", reason="cookie is rejected by Coyote")
    @irrelevant(library="golang", reason="not handled by the Go standard cookie parser")
    def test_cookies_with_semicolon(self):
        """ Cookie with pattern containing a semicolon """
        r = self.weblog_get("/waf", cookies={"value": "%3Bshutdown--"})
        interfaces.library.assert_waf_attack(r, pattern=";shutdown--", address="server.request.cookies")

        r = self.weblog_get("/waf", cookies={"key": ".cookie-%3Bdomain="})
        interfaces.library.assert_waf_attack(r, pattern=".cookie-;domain=", address="server.request.cookies")

    @irrelevant(library="dotnet", reason="One space in the whole value cause kestrel to erase the whole value")
    def test_cookies_with_spaces(self):
        """ Cookie with pattern containing a space """
        r = self.weblog_get("/waf/", cookies={"x-attack": "var_dump ()"})
        interfaces.library.assert_waf_attack(r, pattern="var_dump ()", address="server.request.cookies")

    @irrelevant(library="golang", reason="not handled by the Go standard cookie parser")
    @irrelevant(library="dotnet", reason="Quotation marks cause kestrel to erase the whole value")
    @bug(context.library < "java@0.96.0")
    def test_cookies_with_special_chars2(self):
        """Other cookies patterns"""
        r = self.weblog_get("/waf/", cookies={"x-attack": 'o:4:"x":5:{d}'})
        interfaces.library.assert_waf_attack(r, pattern='o:4:"x":5:{d}', address="server.request.cookies")


@released(golang="?", dotnet="?", java="?", nodejs="?", php_appsec="0.1.0", python="?", ruby="?")
class Test_BodyRaw(BaseTestCase):
    """Appsec supports <body>"""

    @missing_feature(reason="no rule with body raw yet")
    def test_raw_body(self):
        """AppSec detects attacks in raw body"""
        r = self.weblog_post("/waf", data="/.adsensepostnottherenonobook")
        interfaces.library.assert_waf_attack(r, address="server.request.body")


@released(golang="1.37.0", dotnet="?", nodejs="2.2.0", php_appsec="0.1.0", python="?", ruby="?")
@released(
    java="0.100.0"
    if context.weblog_variant == "vertx3"
    else "0.99.0"
    if context.weblog_variant == "ratpack"
    else "0.98.0"
    if context.weblog_variant == "spring-boot-undertow"
    else "0.95.1"
)
class Test_BodyUrlEncoded(BaseTestCase):
    """Appsec supports <url encoded body>"""

    @irrelevant(reason="matching against keys is impossible with current rules")
    def test_body_key(self):
        """AppSec detects attacks in URL encoded body keys"""
        r = self.weblog_post("/waf", data={'<vmlframe src="xss">': "value"})
        interfaces.library.assert_waf_attack(r, pattern="x", address="x")

    def test_body_value(self):
        """AppSec detects attacks in URL encoded body values"""
        r = self.weblog_post("/waf", data={"value": '<vmlframe src="xss">'})
        interfaces.library.assert_waf_attack(r, value='<vmlframe src="xss">', address="server.request.body")


@released(golang="1.37.0", dotnet="?", nodejs="2.2.0", php="?", python="?", ruby="?")
@released(
    java="0.100.0"
    if context.weblog_variant == "vertx3"
    else "0.99.0"
    if context.weblog_variant == "ratpack"
    else "0.95.1"
)
class Test_BodyJson(BaseTestCase):
    """Appsec supports <JSON encoded body>"""

    @irrelevant(reason="matching against keys is impossible with current rules")
    def test_json_key(self):
        """AppSec detects attacks in JSON body keys"""
        r = self.weblog_post("/waf", json={'<vmlframe src="xss">': "value"})
        interfaces.library.assert_waf_attack(r, pattern="x", address="x")

    def test_json_value(self):
        """AppSec detects attacks in JSON body values"""
        r = self.weblog_post("/waf", json={"value": '<vmlframe src="xss">'})
        interfaces.library.assert_waf_attack(r, value='<vmlframe src="xss">', address="server.request.body")

    def test_json_array(self):
        """AppSec detects attacks in JSON body arrays"""
        r = self.weblog_post("/waf", json=['<vmlframe src="xss">'])
        interfaces.library.assert_waf_attack(r, value='<vmlframe src="xss">', address="server.request.body")


@released(golang="1.37.0", dotnet="?", nodejs="2.2.0", php="?", python="?", ruby="?")
@released(
    java="?" if context.weblog_variant == "vertx3" else "0.99.0" if context.weblog_variant == "ratpack" else "0.95.1"
)
class Test_BodyXml(BaseTestCase):
    """Appsec supports <XML encoded body>"""

    ATTACK = '<vmlframe src="xss">'
    ENCODED_ATTACK = "&lt;vmlframe src=&quot;xss&quot;&gt;"

    def weblog_post(self, path="/", params=None, data=None, headers={}, **kwargs):
        headers["Content-Type"] = "application/xml"
        data = f"<?xml version='1.0' encoding='utf-8'?>{data}"
        return super().weblog_post(path, params, data, headers)

    def test_xml_attr_value(self):
        r = self.weblog_post("/waf", data='<a attack="var_dump ()" />', address="server.request.body")
        interfaces.library.assert_waf_attack(r, address="server.request.body", value="var_dump ()")

        r = self.weblog_post("/waf", data=f'<a attack="{self.ENCODED_ATTACK}" />')
        interfaces.library.assert_waf_attack(r, address="server.request.body", value=self.ATTACK)

    def test_xml_content(self):
        r = self.weblog_post("/waf", data="<a>var_dump ()</a>")
        interfaces.library.assert_waf_attack(r, address="server.request.body", value="var_dump ()")

        r = self.weblog_post("/waf", data=f"<a>{self.ENCODED_ATTACK}</a>")
        interfaces.library.assert_waf_attack(r, address="server.request.body", value=self.ATTACK)


@released(golang="?", dotnet="?", java="?", nodejs="?", php="?", python="?", ruby="?")
class Test_Method(BaseTestCase):
    """Appsec supports server.request.method"""

    def test_method(self):
        interfaces.library.append_not_implemented_validation()


@released(golang="?", dotnet="?", java="?", nodejs="?", php="?", python="?", ruby="?")
class Test_ClientIP(BaseTestCase):
    """Appsec supports server.request.client_ip"""

    def test_client_ip(self):
        """ Appsec WAF supports server.request.client_ip """
        interfaces.library.append_not_implemented_validation()


@missing_feature(context.library == "ruby" and context.libddwaf_version is None)
@released(nodejs="2.0.0")
@released(java="0.88.0")
@released(golang="1.36.0")
@released(dotnet="2.3.0")
@released(python="0.58.5")
@missing_feature(context.library <= "golang@1.36.2" and context.weblog_variant == "gin")
class Test_ResponseStatus(BaseTestCase):
    """Appsec supports values on server.response.status"""

    def test_basic(self):
        """ AppSec reports 404 responses"""
        r = self.weblog_get("/mysql")
        interfaces.library.assert_waf_attack(r, pattern="404", address="server.response.status")


@released(dotnet="2.5.1", java="0.95.1", nodejs="2.0.0", php_appsec="0.2.1", python="?", ruby="?")
@released(golang="1.37.0" if context.weblog_variant == "gin" else "1.36.0")
@irrelevant(
    context.library == "golang" and context.weblog_variant == "net-http", reason="net-http doesn't handle path params"
)
class Test_PathParams(BaseTestCase):
    """Appsec supports values on server.request.path_params"""

    @missing_feature(
        context.library == "java" and context.weblog_variant not in ["spring-boot", "spring-boot-jetty"],
        reason="Endpoint is missing in weblog",
    )
    @bug(library="dotnet", reason="attack is not reported")
    def test_security_scanner(self):
        """ AppSec catches attacks in URL path param"""
        r = self.weblog_get("/params/appscan_fingerprint")
        interfaces.library.assert_waf_attack(r, pattern="appscan_fingerprint", address="server.request.path_params")


@released(dotnet="?", golang="1.36.0", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
class Test_gRPC(BaseTestCase):
    """Appsec supports address grpc.server.request.message"""

    def test_basic(self):
        """AppSec detects some basic attack"""
        r = self.weblog_grpc('" OR TRUE --')
        interfaces.library.assert_waf_attack(r, address="grpc.server.request.message")

        r = self.weblog_grpc("SELECT * FROM users WHERE name='com.sun.org.apache' UNION SELECT creditcard FROM users")
        interfaces.library.assert_waf_attack(r, address="grpc.server.request.message")

        r = self.weblog_grpc("SELECT * FROM users WHERE id=1 UNION SELECT creditcard FROM users")
        interfaces.library.assert_waf_attack(r, address="grpc.server.request.message")
