# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


import pytest

from tests.constants import PYTHON_RELEASE_GA_1_1, PYTHON_RELEASE_PUBLIC_BETA
from utils import (
    weblog,
    bug,
    context,
    coverage,
    flaky,
    interfaces,
    irrelevant,
    missing_feature,
    released,
    rfc,
    scenario,
)

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(golang="1.38.1", dotnet="2.7.0", java="0.100.0", nodejs="2.6.0")
@released(php_appsec="0.3.2", python="1.2.1", ruby="1.0.0")
@coverage.basic
class Test_UrlQueryKey:
    """Appsec supports keys on server.request.query"""

    def setup_query_key(self):
        """AppSec catches attacks in URL query key"""
        self.r = weblog.get("/waf/", params={"$eq": "attack"})

    def test_query_key(self):
        """AppSec catches attacks in URL query key"""
        interfaces.library.assert_waf_attack(self.r, pattern="$eq", address="server.request.query")


@released(golang="1.37.0" if context.weblog_variant == "gin" else "1.35.0")
@released(dotnet="1.28.6", java="0.87.0", nodejs="2.0.0", php_appsec="0.1.0", python="1.2.1", ruby="0.54.2")
@coverage.good
class Test_UrlQuery:
    """Appsec supports values on server.request.query"""

    def setup_query_argument(self):
        self.r_query_argument = weblog.get("/waf/", params={"attack": "appscan_fingerprint"})

    def test_query_argument(self):
        """AppSec catches attacks in URL query value"""
        interfaces.library.assert_waf_attack(
            self.r_query_argument, pattern="appscan_fingerprint", address="server.request.query"
        )

    def setup_query_encoded(self):
        self.r_query_encoded = weblog.get("/waf/", params={"key": "<script>"})

    def test_query_encoded(self):
        """AppSec catches attacks in URL query value, even encoded"""
        interfaces.library.assert_waf_attack(self.r_query_encoded, address="server.request.query")

    def setup_query_with_strict_regex(self):
        self.r_query_with_strict_regex = weblog.get("/waf/", params={"value": "0000012345"})

    @irrelevant(context.agent_version >= "1.2.6", reason="Need to find another rule")
    def test_query_with_strict_regex(self):
        """AppSec catches attacks in URL query value, even with regex containing start and end char"""
        interfaces.library.assert_waf_attack(
            self.r_query_with_strict_regex, pattern="0000012345", address="server.request.query"
        )


@released(golang={"gin": "1.37.0", "chi": "1.36.0", "echo": "1.36.0", "*": "1.34.0"})
@released(dotnet="1.28.6", java="0.87.0")
@released(nodejs="2.0.0", php_appsec="0.1.0", python="0.58.5")
@flaky(context.library <= "php@0.68.2")
@coverage.basic
class Test_UrlRaw:
    """Appsec supports server.request.uri.raw"""

    def setup_path(self):
        self.r = weblog.get("/waf/0x5c0x2e0x2e0x2f")

    def test_path(self):
        """AppSec catches attacks in raw URL path"""
        interfaces.library.assert_waf_attack(self.r, pattern="0x5c0x2e0x2e0x2f", address="server.request.uri.raw")


@released(golang={"gin": "1.37.0", "chi": "1.36.0", "echo": "1.36.0", "*": "1.34.0"})
@released(dotnet="1.28.6", java="0.87.0")
@released(nodejs="2.0.0", php_appsec="0.1.0")
@released(python="1.1.0rc2.dev")
@flaky(context.library <= "php@0.68.2")
@bug(library="python@1.1.0", reason="a PR was not included in the release")
@coverage.good
class Test_Headers:
    """Appsec supports server.request.headers.no_cookies"""

    def setup_value(self):
        self.r_value = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_value(self):
        """Appsec WAF detects attacks in header value"""

        interfaces.library.assert_waf_attack(
            self.r_value, pattern="Arachni/v", address="server.request.headers.no_cookies", key_path=["user-agent"]
        )

    def setup_specific_key(self):
        self.r_sk_1 = weblog.get("/waf/", headers={"x-file-name": "routing.yml"})
        self.r_sk_2 = weblog.get("/waf/", headers={"X-File-Name": "routing.yml"})
        self.r_sk_3 = weblog.get("/waf/", headers={"X-Filename": "routing.yml"})

    def test_specific_key(self):
        """Appsec WAF detects attacks on specific header x-file-name or referer, and report it"""
        interfaces.library.assert_waf_attack(
            self.r_sk_1, pattern="routing.yml", address="server.request.headers.no_cookies", key_path=["x-file-name"]
        )

        interfaces.library.assert_waf_attack(
            self.r_sk_2, pattern="routing.yml", address="server.request.headers.no_cookies", key_path=["x-file-name"]
        )

        interfaces.library.assert_waf_attack(
            self.r_sk_3, pattern="routing.yml", address="server.request.headers.no_cookies", key_path=["x-filename"]
        )

    def setup_specific_key2(self):
        self.r_sk_4 = weblog.get("/waf/", headers={"X_Filename": "routing.yml"})

    @missing_feature(library="python")
    @irrelevant(library="ruby", reason="Rack transforms underscores into dashes")
    @irrelevant(library="php", reason="PHP normalizes into dashes; additionally, matching on keys is not supported")
    def test_specific_key2(self):
        """attacks on specific header X_Filename, and report it"""

        interfaces.library.assert_waf_attack(
            self.r_sk_4, pattern="routing.yml", address="server.request.headers.no_cookies", key_path=["x_filename"]
        )

    def setup_specific_key3(self):
        self.r_sk_5 = weblog.get("/waf/", headers={"referer": "<script >"})
        self.r_sk_6 = weblog.get("/waf/", headers={"RefErEr": "<script >"})

    def test_specific_key3(self):
        """When a specific header key is specified, other key are ignored"""
        ADDRESS = "server.request.headers.no_cookies"
        interfaces.library.assert_waf_attack(self.r_sk_5, address=ADDRESS, key_path=["referer"])
        interfaces.library.assert_waf_attack(self.r_sk_6, address=ADDRESS, key_path=["referer"])

    def setup_specific_wrong_key(self):
        self.r_wk_1 = weblog.get("/waf/", headers={"xfilename": "routing.yml"})
        self.r_wk_2 = weblog.get("/waf/", headers={"not-referer": "<script >"})

    def test_specific_wrong_key(self):
        """When a specific header key is specified in rules, other key are ignored"""
        interfaces.library.assert_no_appsec_event(self.r_wk_1)
        interfaces.library.assert_no_appsec_event(self.r_wk_2)


@released(golang={"gin": "1.37.0", "chi": "1.36.0", "echo": "1.36.0", "*": "1.34.0"})
@released(nodejs="2.0.0", php_appsec="0.1.0")
@released(
    python={
        "django-poc": "1.1.0rc2.dev",
        "flask-poc": PYTHON_RELEASE_PUBLIC_BETA,
        "uwsgi-poc": "?",
        "pylons": "1.1.0rc2.dev",
    }
)
@coverage.good
class Test_Cookies:
    """Appsec supports server.request.cookies"""

    # Cookies rules has been removed in rules version 1.2.7. Test on cookies are now done on custom rules scenario.
    # Once we have rules with cookie back in the default rules set, we can re-use this class to validated this feature

    def setup_cookies(self):
        self.r_cookies = weblog.get("/waf/", cookies={"attack": ".htaccess"})

    @irrelevant(context.appsec_rules_version >= "1.2.7", reason="cookies were disabled for the time being")
    def test_cookies(self):
        """Appsec WAF detects attackes in cookies"""
        interfaces.library.assert_waf_attack(self.r_cookies, pattern=".htaccess", address="server.request.cookies")

    def setup_cookies_with_semicolon(self):
        self.r_cwsc_1 = weblog.get("/waf", cookies={"value": "%3Bshutdown--"})
        self.r_cwsc_2 = weblog.get("/waf", cookies={"key": ".cookie-%3Bdomain="})

    @irrelevant(
        library="java",
        reason="cookies are not urldecoded; see RFC 6265, which only suggests they be base64 "
        "encoded to represent disallowed octets",
    )
    @irrelevant(library="golang", reason="not handled by the Go standard cookie parser")
    @irrelevant(context.appsec_rules_version >= "1.2.7", reason="cookies were disabled for the time being")
    def test_cookies_with_semicolon(self):
        """Cookie with pattern containing a semicolon"""
        interfaces.library.assert_waf_attack(self.r_cwsc_1, pattern=";shutdown--", address="server.request.cookies")
        interfaces.library.assert_waf_attack(
            self.r_cwsc_2, pattern=".cookie-;domain=", address="server.request.cookies"
        )

    def setup_cookies_with_spaces(self):
        self.r_cws = weblog.get("/waf/", cookies={"x-attack": "var_dump ()"})

    @irrelevant(library="dotnet", reason="One space in the whole value cause kestrel to erase the whole value")
    @irrelevant(context.appsec_rules_version >= "1.2.7", reason="cookies were disabled for the time being")
    def test_cookies_with_spaces(self):
        """Cookie with pattern containing a space"""
        interfaces.library.assert_waf_attack(self.r_cws, pattern="var_dump ()", address="server.request.cookies")

    def setup_cookies_with_special_chars2(self):
        self.r_cwsc2 = weblog.get("/waf/", cookies={"x-attack": 'o:4:"x":5:{d}'})

    @irrelevant(library="golang", reason="not handled by the Go standard cookie parser")
    @irrelevant(library="dotnet", reason="Quotation marks cause kestrel to erase the whole value")
    @bug(context.library < "java@0.96.0")
    @irrelevant(context.appsec_rules_version >= "1.2.7", reason="cookies were disabled for the time being")
    def test_cookies_with_special_chars2(self):
        """Other cookies patterns"""
        interfaces.library.assert_waf_attack(self.r_cwsc2, pattern='o:4:"x":5:{d}', address="server.request.cookies")

    def setup_cookies_custom_rules(self):
        self.r_ccr = weblog.get("/waf/", cookies={"attack": ".htaccess"})

    @scenario("APPSEC_CUSTOM_RULES")
    def test_cookies_custom_rules(self):
        """ Appsec WAF detects attackes in cookies """
        interfaces.library.assert_waf_attack(self.r_ccr, pattern=".htaccess", address="server.request.cookies")

    def setup_cookies_with_semicolon_custom_rules(self):
        self.r_cwsccr = weblog.get("/waf", cookies={"value": "%3Bshutdown--"})

    @irrelevant(
        library="java",
        reason="cookies are not urldecoded; see RFC 6265, which only suggests they be base64 "
        "encoded to represent disallowed octets",
    )
    @irrelevant(library="golang", reason="Not handled by the Go standard cookie parser")
    @irrelevant(library="python", reason="Not handled by the Python standard cookie parser")
    @scenario("APPSEC_CUSTOM_RULES")
    def test_cookies_with_semicolon_custom_rules(self):
        """ Cookie with pattern containing a semicolon """
        interfaces.library.assert_waf_attack(self.r_cwsccr, pattern=";shutdown--", address="server.request.cookies")

    def setup_cookies_with_spaces_custom_rules(self):
        self.r_cwscr_2 = weblog.get("/waf/", cookies={"x-attack": "var_dump ()"})

    @irrelevant(library="dotnet", reason="One space in the whole value cause kestrel to erase the whole value")
    @scenario("APPSEC_CUSTOM_RULES")
    def test_cookies_with_spaces_custom_rules(self):
        """ Cookie with pattern containing a space """
        interfaces.library.assert_waf_attack(self.r_cwscr_2, pattern="var_dump ()", address="server.request.cookies")

    def setup_cookies_with_special_chars2_custom_rules(self):
        """Other cookies patterns"""
        self.r_cwsc2cc = weblog.get("/waf/", cookies={"x-attack": 'o:4:"x":5:{d}'})

    @irrelevant(library="golang", reason="Not handled by the Go standard cookie parser")
    @irrelevant(library="dotnet", reason="Quotation marks cause kestrel to erase the whole value")
    @bug(context.library < "java@0.96.0")
    @scenario("APPSEC_CUSTOM_RULES")
    def test_cookies_with_special_chars2_custom_rules(self):
        """Other cookies patterns"""
        interfaces.library.assert_waf_attack(self.r_cwsc2cc, pattern='o:4:"x":5:{d}', address="server.request.cookies")


@released(golang="?", dotnet="?", java="?", nodejs="?", php_appsec="0.1.0", ruby="?")
@released(python={"django-poc": "1.5.2", "*": "?"})
@coverage.basic
class Test_BodyRaw:
    """Appsec supports <body>"""

    def setup_raw_body(self):
        self.r = weblog.post("/waf", data="/.adsensepostnottherenonobook")

    @missing_feature(reason="no rule with body raw yet")
    def test_raw_body(self):
        """AppSec detects attacks in raw body"""
        interfaces.library.assert_waf_attack(self.r, address="server.request.body")


@released(golang="1.37.0", dotnet="2.7.0", nodejs="2.2.0", php_appsec="0.1.0", python="1.4.0rc1.dev", ruby="?")
@released(java={"vertx3": "0.99.0", "ratpack": "0.99.0", "spring-boot-undertow": "0.98.0", "*": "0.95.1"})
@coverage.basic
@bug(context.library == "nodejs@2.8.0", reason="Capability to read body content is broken")
class Test_BodyUrlEncoded:
    """Appsec supports <url encoded body>"""

    def setup_body_key(self):
        self.r_key = weblog.post("/waf", data={'<vmlframe src="xss">': "value"})

    @irrelevant(reason="matching against keys is impossible with current rules")
    def test_body_key(self):
        """AppSec detects attacks in URL encoded body keys"""
        interfaces.library.assert_waf_attack(self.r_key, pattern="x", address="x")

    def setup_body_value(self):
        """AppSec detects attacks in URL encoded body values"""
        self.r_value = weblog.post("/waf", data={"value": '<vmlframe src="xss">'})

    @bug(
        library="java",
        weblog_variant="spring-boot-openliberty",
        reason="https://datadoghq.atlassian.net/browse/APPSEC-6583",
    )
    def test_body_value(self):
        """AppSec detects attacks in URL encoded body values"""
        interfaces.library.assert_waf_attack(self.r_value, value='<vmlframe src="xss">', address="server.request.body")


@released(golang="1.37.0", dotnet="2.8.0", nodejs="2.2.0", php="?", python="1.4.0rc1.dev", ruby="?")
@released(java={"vertx3": "0.99.0", "ratpack": "0.99.0", "*": "0.95.1"})
@coverage.basic
@bug(context.library == "nodejs@2.8.0", reason="Capability to read body content is broken")
class Test_BodyJson:
    """Appsec supports <JSON encoded body>"""

    def setup_json_key(self):
        """AppSec detects attacks in JSON body keys"""
        self.r_key = weblog.post("/waf", json={'<vmlframe src="xss">': "value"})

    @irrelevant(reason="matching against keys is impossible with current rules")
    def test_json_key(self):
        """AppSec detects attacks in JSON body keys"""
        interfaces.library.assert_waf_attack(self.r_key, pattern="x", address="x")

    def setup_json_value(self):
        """AppSec detects attacks in JSON body values"""
        self.r_value = weblog.post("/waf", json={"value": '<vmlframe src="xss">'})

    def test_json_value(self):
        """AppSec detects attacks in JSON body values"""
        interfaces.library.assert_waf_attack(self.r_value, value='<vmlframe src="xss">', address="server.request.body")

    def setup_json_array(self):
        self.r_array = weblog.post("/waf", json=['<vmlframe src="xss">'])

    @irrelevant(reason="unsupported by framework", library="ruby", weblog_variant="rack")
    @irrelevant(reason="unsupported by framework", library="ruby", weblog_variant="sinatra14")
    @irrelevant(reason="unsupported by framework", library="ruby", weblog_variant="sinatra20")
    @irrelevant(reason="unsupported by framework", library="ruby", weblog_variant="sinatra21")
    def test_json_array(self):
        """AppSec detects attacks in JSON body arrays"""
        interfaces.library.assert_waf_attack(self.r_array, value='<vmlframe src="xss">', address="server.request.body")


@released(golang="1.37.0", dotnet="2.8.0", nodejs="2.2.0", php="?", python=PYTHON_RELEASE_GA_1_1, ruby="?")
@released(java={"vertx3": "?", "ratpack": "0.99.0", "*": "0.95.1"})
@bug(context.library == "nodejs@2.8.0", reason="Capability to read body content is broken")
@coverage.basic
class Test_BodyXml:
    """Appsec supports <XML encoded body>"""

    ATTACK = '<vmlframe src="xss">'
    ENCODED_ATTACK = "&lt;vmlframe src=&quot;xss&quot;&gt;"

    def weblog_post(self, path="/", params=None, data=None, headers=None, **kwargs):
        headers = headers or {}
        headers["Content-Type"] = "application/xml"
        data = f"<?xml version='1.0' encoding='utf-8'?>{data}"
        return weblog.post(path, params, data, headers)

    def setup_xml_attr_value(self):
        self.r_attr_1 = self.weblog_post("/waf", data='<string attack="var_dump ()" />')
        self.r_attr_2 = self.weblog_post("/waf", data=f'<string attack="{self.ENCODED_ATTACK}" />')

    def test_xml_attr_value(self):
        interfaces.library.assert_waf_attack(self.r_attr_1, address="server.request.body", value="var_dump ()")
        interfaces.library.assert_waf_attack(self.r_attr_2, address="server.request.body", value=self.ATTACK)

    def setup_xml_content(self):
        self.r_content_1 = self.weblog_post("/waf", data="<string>var_dump ()</string>")
        self.r_content_2 = self.weblog_post("/waf", data=f"<string>{self.ENCODED_ATTACK}</string>")

    def test_xml_content(self):
        interfaces.library.assert_waf_attack(self.r_content_1, address="server.request.body", value="var_dump ()")
        interfaces.library.assert_waf_attack(self.r_content_2, address="server.request.body", value=self.ATTACK)


@released(golang="?", dotnet="?", java="?", nodejs="?", php="?", python="?", ruby="?")
@coverage.not_implemented
class Test_Method:
    """Appsec supports server.request.method"""


@released(golang="?", dotnet="?", java="?", nodejs="?", php="?", python=PYTHON_RELEASE_GA_1_1, ruby="?")
@coverage.not_implemented
class Test_ClientIP:
    """Appsec supports server.request.client_ip"""


@missing_feature(context.library == "ruby" and context.libddwaf_version is None)
@released(golang="1.37.0" if context.weblog_variant == "gin" else "1.36.0")
@released(dotnet="2.3.0", java="0.88.0", nodejs="2.0.0", python="0.58.5")
@coverage.good
class Test_ResponseStatus:
    """Appsec supports values on server.response.status"""

    def setup_basic(self):
        self.r = weblog.get("/mysql")

    @bug(
        library="java",
        weblog_variant="spring-boot-openliberty",
        reason="https://datadoghq.atlassian.net/browse/APPSEC-6583",
    )
    def test_basic(self):
        """AppSec reports 404 responses"""
        interfaces.library.assert_waf_attack(self.r, pattern="404", address="server.response.status")


@released(dotnet="2.5.1", nodejs="2.0.0", php_appsec="0.2.1", ruby="?")
@released(java={"vertx3": "0.99.0", "ratpack": "0.99.0", "resteasy-netty3": "?", "jersey-grizzly2": "?", "*": "0.95.1"})
@released(golang={"gin": "1.37.0", "*": "1.36.0"})
@released(
    python={
        "django-poc": "1.1.0rc2.dev",
        "flask-poc": PYTHON_RELEASE_PUBLIC_BETA,
        "uwsgi-poc": "1.5.2",
        "pylons": "1.1.0rc2.dev",
    }
)
@irrelevant(
    context.library == "golang" and context.weblog_variant == "net-http", reason="net-http doesn't handle path params"
)
@coverage.basic
class Test_PathParams:
    """Appsec supports values on server.request.path_params"""

    def setup_security_scanner(self):
        self.r = weblog.get("/params/appscan_fingerprint")

    def test_security_scanner(self):
        """AppSec catches attacks in URL path param"""
        interfaces.library.assert_waf_attack(
            self.r, pattern="appscan_fingerprint", address="server.request.path_params"
        )


@released(golang="1.36.0", dotnet="?", java="0.96.0", nodejs="?", php_appsec="?", python="?", ruby="?")
@irrelevant(context.library == "java" and context.weblog_variant != "spring-boot")
@bug(context.library < "java@0.109.0", weblog_variant="spring-boot", reason="APPSEC-5426")
@coverage.basic
class Test_gRPC:
    """Appsec supports address grpc.server.request.message"""

    def setup_basic(self):
        self.requests = [
            weblog.grpc('" OR TRUE --'),
            weblog.grpc("SELECT * FROM users WHERE name='com.sun.org.apache' UNION SELECT creditcard FROM users"),
            weblog.grpc("SELECT * FROM users WHERE id=1 UNION SELECT creditcard FROM users"),
        ]

    def test_basic(self):
        """AppSec detects some basic attack"""
        for r in self.requests:
            interfaces.library.assert_waf_attack(r, address="grpc.server.request.message")


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2278064284/gRPC+Protocol+Support")
@coverage.not_implemented
@released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
class Test_FullGrpc:
    """Full gRPC support"""


@coverage.not_implemented
@released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
class Test_GraphQL:
    """GraphQL support"""


@coverage.not_implemented
@released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
class Test_Lambda:
    """Lambda support"""
