# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


from utils import context, BaseTestCase, interfaces, released, bug, irrelevant, missing_feature, flaky, coverage, rfc
import pytest


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(golang="1.38.1", dotnet="2.7.0", java="0.100.0", nodejs="2.6.0")
@released(php_appsec="0.3.2", python="1.2.1", ruby="1.0.0")
@coverage.basic
class Test_UrlQueryKey(BaseTestCase):
    """Appsec supports keys on server.request.query"""

    def test_query_key(self):
        """AppSec catches attacks in URL query key"""
        r = self.weblog_get("/waf/", params={"$eq": "attack"})
        interfaces.library.assert_waf_attack(r, pattern="$eq", address="server.request.query")


@released(golang="1.37.0" if context.weblog_variant == "gin" else "1.35.0")
@released(dotnet="1.28.6", java="0.87.0", nodejs="2.0.0", php_appsec="0.1.0", python="1.2.1", ruby="0.54.2")
@coverage.good
class Test_UrlQuery(BaseTestCase):
    """Appsec supports values on server.request.query"""

    def test_query_argument(self):
        """AppSec catches attacks in URL query value"""
        r = self.weblog_get("/waf/", params={"attack": "appscan_fingerprint"})
        interfaces.library.assert_waf_attack(r, pattern="appscan_fingerprint", address="server.request.query")

    def test_query_encoded(self):
        """AppSec catches attacks in URL query value, even encoded"""
        r = self.weblog_get("/waf/", params={"key": "<script>"})
        interfaces.library.assert_waf_attack(r, address="server.request.query")

    @irrelevant(context.agent_version >= "1.2.6", reason="Need to find another rule")
    def test_query_with_strict_regex(self):
        """AppSec catches attacks in URL query value, even with regex containing start and end char"""
        r = self.weblog_get("/waf/", params={"value": "0000012345"})
        interfaces.library.assert_waf_attack(r, pattern="0000012345", address="server.request.query")


@released(
    golang="1.37.0"
    if context.weblog_variant == "gin"
    else "1.36.0"
    if context.weblog_variant in ["echo", "chi"]
    else "1.34.0"
)
@released(dotnet="1.28.6", java="0.87.0")
@released(nodejs="2.0.0", php_appsec="0.1.0", python="0.58.5")
@flaky(context.library <= "php@0.68.2")
@coverage.basic
class Test_UrlRaw(BaseTestCase):
    """Appsec supports server.request.uri.raw"""

    def test_path(self):
        """AppSec catches attacks in raw URL path"""
        r = self.weblog_get("/waf/0x5c0x2e0x2e0x2f")
        interfaces.library.assert_waf_attack(r, pattern="0x5c0x2e0x2e0x2f", address="server.request.uri.raw")


@released(
    golang="1.37.0"
    if context.weblog_variant == "gin"
    else "1.36.0"
    if context.weblog_variant in ["echo", "chi"]
    else "1.34.0"
)
@released(dotnet="1.28.6", java="0.87.0")
@released(nodejs="2.0.0", php_appsec="0.1.0")
@released(python="1.1.0rc2.dev")
@flaky(context.library <= "php@0.68.2")
@bug(library="python@1.1.0", reason="a PR was not included in the release")
@coverage.good
class Test_Headers(BaseTestCase):
    """Appsec supports server.request.headers.no_cookies"""

    def test_value(self):
        """Appsec WAF detects attacks in header value"""
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.assert_waf_attack(
            r, pattern="Arachni/v", address="server.request.headers.no_cookies", key_path=["user-agent"]
        )

    def test_specific_key(self):
        """Appsec WAF detects attacks on specific header x-file-name or referer, and report it"""
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
        """attacks on specific header X_Filename, and report it"""
        r = self.weblog_get("/waf/", headers={"X_Filename": "routing.yml"})
        interfaces.library.assert_waf_attack(
            r, pattern="routing.yml", address="server.request.headers.no_cookies", key_path=["x_filename"]
        )

    def test_specific_key3(self):
        """When a specific header key is specified, other key are ignored"""
        r = self.weblog_get("/waf/", headers={"referer": "<script >"})
        interfaces.library.assert_waf_attack(r, address="server.request.headers.no_cookies", key_path=["referer"])

        r = self.weblog_get("/waf/", headers={"RefErEr": "<script >"})
        interfaces.library.assert_waf_attack(r, address="server.request.headers.no_cookies", key_path=["referer"])

    def test_specific_wrong_key(self):
        """When a specific header key is specified in rules, other key are ignored"""
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
@released(nodejs="2.0.0", php_appsec="0.1.0", python="1.3.0rc2.dev")
@coverage.good
class Test_Cookies(BaseTestCase):
    """Appsec supports server.request.cookies"""

    # Cookies rules has been removed in rules version 1.2.7. Test on cookies are now done on custom rules scenario.
    # Once we have rules with cookie back in the default rules set, we can re-use this class to validated this feature

    def test_cookies(self):
        """Appsec WAF detects attackes in cookies"""
        r = self.weblog_get("/waf/", cookies={"attack": ".htaccess"})
        interfaces.library.assert_waf_attack(r, pattern=".htaccess", address="server.request.cookies")

    @irrelevant(
        library="java",
        reason="cookies are not urldecoded; see RFC 6265, which only suggests they be base64 "
        "encoded to represent disallowed octets",
    )
    @irrelevant(library="golang", reason="not handled by the Go standard cookie parser")
    def test_cookies_with_semicolon(self):
        """Cookie with pattern containing a semicolon"""
        r = self.weblog_get("/waf", cookies={"value": "%3Bshutdown--"})
        interfaces.library.assert_waf_attack(r, pattern=";shutdown--", address="server.request.cookies")

        r = self.weblog_get("/waf", cookies={"key": ".cookie-%3Bdomain="})
        interfaces.library.assert_waf_attack(r, pattern=".cookie-;domain=", address="server.request.cookies")

    @irrelevant(library="dotnet", reason="One space in the whole value cause kestrel to erase the whole value")
    def test_cookies_with_spaces(self):
        """Cookie with pattern containing a space"""
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
@coverage.basic
class Test_BodyRaw(BaseTestCase):
    """Appsec supports <body>"""

    @missing_feature(reason="no rule with body raw yet")
    def test_raw_body(self):
        """AppSec detects attacks in raw body"""
        r = self.weblog_post("/waf", data="/.adsensepostnottherenonobook")
        interfaces.library.assert_waf_attack(r, address="server.request.body")


@released(golang="1.37.0", dotnet="2.7.0", nodejs="2.2.0", php_appsec="0.1.0", python="?", ruby="?")
@released(
    java="0.99.0"
    if context.weblog_variant == "vertx3"
    else "0.99.0"
    if context.weblog_variant == "ratpack"
    else "0.98.0"
    if context.weblog_variant == "spring-boot-undertow"
    else "0.95.1"
)
@coverage.basic
@bug(context.library == "nodejs@2.8.0", reason="Capability to read body content is broken")
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


@released(golang="1.37.0", dotnet="2.8.0", nodejs="2.2.0", php="?", python="?", ruby="?")
@released(
    java="0.99.0"
    if context.weblog_variant == "vertx3"
    else "0.99.0"
    if context.weblog_variant == "ratpack"
    else "0.95.1"
)
@coverage.basic
@bug(context.library == "nodejs@2.8.0", reason="Capability to read body content is broken")
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

    @irrelevant(reason="unsupported by framework", library="ruby", weblog_variant="rack")
    @irrelevant(reason="unsupported by framework", library="ruby", weblog_variant="sinatra14")
    @irrelevant(reason="unsupported by framework", library="ruby", weblog_variant="sinatra20")
    @irrelevant(reason="unsupported by framework", library="ruby", weblog_variant="sinatra21")
    def test_json_array(self):
        """AppSec detects attacks in JSON body arrays"""
        r = self.weblog_post("/waf", json=['<vmlframe src="xss">'])
        interfaces.library.assert_waf_attack(r, value='<vmlframe src="xss">', address="server.request.body")


@released(golang="1.37.0", dotnet="2.8.0", nodejs="2.2.0", php="?", python="?", ruby="?")
@released(
    java="?" if context.weblog_variant == "vertx3" else "0.99.0" if context.weblog_variant == "ratpack" else "0.95.1"
)
@coverage.basic
@bug(context.library == "nodejs@2.8.0", reason="Capability to read body content is broken")
class Test_BodyXml(BaseTestCase):
    """Appsec supports <XML encoded body>"""

    ATTACK = '<vmlframe src="xss">'
    ENCODED_ATTACK = "&lt;vmlframe src=&quot;xss&quot;&gt;"

    def weblog_post(self, path="/", params=None, data=None, headers=None, **kwargs):
        headers = headers or {}
        headers["Content-Type"] = "application/xml"
        data = f"<?xml version='1.0' encoding='utf-8'?>{data}"
        return super().weblog_post(path, params, data, headers)

    def test_xml_attr_value(self):
        r = self.weblog_post("/waf", data='<string attack="var_dump ()" />', address="server.request.body")
        interfaces.library.assert_waf_attack(r, address="server.request.body", value="var_dump ()")

        r = self.weblog_post("/waf", data=f'<string attack="{self.ENCODED_ATTACK}" />')
        interfaces.library.assert_waf_attack(r, address="server.request.body", value=self.ATTACK)

    def test_xml_content(self):
        r = self.weblog_post("/waf", data="<string>var_dump ()</string>")
        interfaces.library.assert_waf_attack(r, address="server.request.body", value="var_dump ()")

        r = self.weblog_post("/waf", data=f"<string>{self.ENCODED_ATTACK}</string>")
        interfaces.library.assert_waf_attack(r, address="server.request.body", value=self.ATTACK)


@released(golang="?", dotnet="?", java="?", nodejs="?", php="?", python="?", ruby="?")
@coverage.not_implemented
class Test_Method(BaseTestCase):
    """Appsec supports server.request.method"""


@released(golang="?", dotnet="?", java="?", nodejs="?", php="?", python="?", ruby="?")
@coverage.not_implemented
class Test_ClientIP(BaseTestCase):
    """Appsec supports server.request.client_ip"""


@missing_feature(context.library == "ruby" and context.libddwaf_version is None)
@released(golang="1.37.0" if context.weblog_variant == "gin" else "1.36.0")
@released(dotnet="2.3.0", java="0.88.0", nodejs="2.0.0", python="0.58.5")
@coverage.good
class Test_ResponseStatus(BaseTestCase):
    """Appsec supports values on server.response.status"""

    def test_basic(self):
        """AppSec reports 404 responses"""
        r = self.weblog_get("/mysql")
        interfaces.library.assert_waf_attack(r, pattern="404", address="server.response.status")


@released(dotnet="2.5.1", nodejs="2.0.0", php_appsec="0.2.1", python="1.1.0rc2.dev", ruby="?")
@released(golang="1.37.0" if context.weblog_variant == "gin" else "1.36.0")
@released(
    java="?"
    if context.weblog_variant in ["jersey-grizzly2", "resteasy-netty3"]
    else "0.99.0"
    if context.weblog_variant in ["vertx3", "ratpack"]
    else "0.95.1"
)
@irrelevant(
    context.library == "golang" and context.weblog_variant == "net-http", reason="net-http doesn't handle path params"
)
@coverage.basic
class Test_PathParams(BaseTestCase):
    """Appsec supports values on server.request.path_params"""

    @missing_feature(context.weblog_variant == "uwsgi-poc")
    def test_security_scanner(self):
        """AppSec catches attacks in URL path param"""
        r = self.weblog_get("/params/appscan_fingerprint")
        interfaces.library.assert_waf_attack(r, pattern="appscan_fingerprint", address="server.request.path_params")


@released(golang="1.36.0", dotnet="?", java="0.96.0", nodejs="?", php_appsec="?", python="?", ruby="?")
@irrelevant(context.library == "java" and context.weblog_variant != "spring-boot")
@coverage.basic
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


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2278064284/gRPC+Protocol+Support")
@coverage.not_implemented
@released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
class Test_FullGrpc:
    """ Full gRPC support"""


@coverage.not_implemented
@released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
class Test_GraphQL:
    """ GraphQL support"""


@coverage.not_implemented
@released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
class Test_Lambda:
    """ Lambda support"""
