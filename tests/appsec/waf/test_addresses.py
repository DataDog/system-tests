# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import json
import pytest
from utils import weblog, bug, context, interfaces, irrelevant, missing_feature, rfc, scenarios, features, logger


@features.appsec_request_blocking
class Test_UrlQueryKey:
    """Appsec supports keys on server.request.query"""

    def setup_query_key(self):
        """AppSec catches attacks in URL query key"""
        self.r = weblog.get("/waf/", params={"$eq": "attack"})

    def test_query_key(self):
        """AppSec catches attacks in URL query key"""
        interfaces.library.assert_waf_attack(self.r, pattern="$eq", address="server.request.query")


@features.appsec_request_blocking
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


@features.appsec_request_blocking
class Test_UrlRaw:
    """Appsec supports server.request.uri.raw"""

    def setup_path(self):
        self.r = weblog.get("/waf/0x5c0x2e0x2e0x2f")

    def test_path(self):
        """AppSec catches attacks in raw URL path"""
        interfaces.library.assert_waf_attack(self.r, pattern="0x5c0x2e0x2e0x2f", address="server.request.uri.raw")


@features.appsec_request_blocking
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

    @irrelevant(library="ruby", reason="Rack transforms underscores into dashes")
    @irrelevant(library="php", reason="PHP normalizes into dashes; additionally, matching on keys is not supported")
    @irrelevant(library="cpp_nginx", reason="Header rejected by nginx ('client sent invalid header line'")
    @missing_feature(weblog_variant="spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_specific_key2(self):
        """Attacks on specific header X_Filename, and report it"""
        try:
            interfaces.library.assert_waf_attack(
                self.r_sk_4, pattern="routing.yml", address="server.request.headers.no_cookies", key_path=["x_filename"]
            )
        except ValueError:
            # also accept report on x-filename
            interfaces.library.assert_waf_attack(
                self.r_sk_4, pattern="routing.yml", address="server.request.headers.no_cookies", key_path=["x-filename"]
            )

    def setup_specific_key3(self):
        self.r_sk_5 = weblog.get("/waf/", headers={"referer": "<script >"})
        self.r_sk_6 = weblog.get("/waf/", headers={"RefErEr": "<script >"})

    def test_specific_key3(self):
        """When a specific header key is specified, other key are ignored"""
        address = "server.request.headers.no_cookies"
        interfaces.library.assert_waf_attack(self.r_sk_5, address=address, key_path=["referer"])
        interfaces.library.assert_waf_attack(self.r_sk_6, address=address, key_path=["referer"])

    def setup_specific_wrong_key(self):
        self.r_wk_1 = weblog.get("/waf/", headers={"xfilename": "routing.yml"})
        self.r_wk_2 = weblog.get("/waf/", headers={"not-referer": "<script >"})

    @missing_feature(weblog_variant="spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_specific_wrong_key(self):
        """When a specific header key is specified in rules, other key are ignored"""
        for r in [self.r_wk_1, self.r_wk_2]:
            logger.debug(f"Testing {r.request.headers}")
            assert r.status_code == 200
            spans = [span for _, span in interfaces.library.get_root_spans(request=r)]
            assert spans, "No spans to validate"
            assert any("_dd.appsec.enabled" in s.get("metrics", {}) for s in spans), "No appsec-enabled spans found"
        interfaces.library.assert_no_appsec_event(self.r_wk_1)
        interfaces.library.assert_no_appsec_event(self.r_wk_2)


@features.appsec_request_blocking
class Test_Cookies:
    """Appsec supports server.request.cookies"""

    # Cookies rules has been removed in rules version 1.2.7. Test on cookies are now done on custom rules scenario.
    # Once we have rules with cookie back in the default rules set, we can re-use this class to validated this feature

    def setup_cookies_custom_rules(self):
        self.r_ccr = weblog.get("/waf/", cookies={"attack": ".htaccess"})

    @scenarios.appsec_custom_rules
    def test_cookies_custom_rules(self):
        """Appsec WAF detects attackes in cookies"""
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
    @scenarios.appsec_custom_rules
    def test_cookies_with_semicolon_custom_rules(self):
        """Cookie with pattern containing a semicolon"""
        interfaces.library.assert_waf_attack(self.r_cwsccr, pattern=";shutdown--", address="server.request.cookies")

    def setup_cookies_with_spaces_custom_rules(self):
        self.r_cwscr_2 = weblog.get("/waf/", cookies={"x-attack": "var_dump ()"})

    @irrelevant(library="dotnet", reason="One space in the whole value cause kestrel to erase the whole value")
    @scenarios.appsec_custom_rules
    def test_cookies_with_spaces_custom_rules(self):
        """Cookie with pattern containing a space"""
        interfaces.library.assert_waf_attack(self.r_cwscr_2, pattern="var_dump ()", address="server.request.cookies")

    def setup_cookies_with_special_chars2_custom_rules(self):
        """Other cookies patterns"""
        self.r_cwsc2cc = weblog.get("/waf/", cookies={"x-attack": 'o:4:"x":5:{d}'})

    @irrelevant(library="golang", reason="Not handled by the Go standard cookie parser")
    @irrelevant(library="dotnet", reason="Quotation marks cause kestrel to erase the whole value")
    @bug(context.library < "java@0.96.0", reason="APMRP-360")
    @scenarios.appsec_custom_rules
    def test_cookies_with_special_chars2_custom_rules(self):
        """Other cookies patterns"""
        interfaces.library.assert_waf_attack(self.r_cwsc2cc, pattern='o:4:"x":5:{d}', address="server.request.cookies")


@features.appsec_request_blocking
class Test_BodyRaw:
    """Appsec supports <body>"""

    def setup_raw_body(self):
        self.r = weblog.post("/waf", data="/.adsensepostnottherenonobook")

    @irrelevant(reason="no rule with body raw yet")
    def test_raw_body(self):
        """AppSec detects attacks in raw body"""
        interfaces.library.assert_waf_attack(self.r, address="server.request.body.raw")


@bug(context.library == "nodejs@2.8.0", reason="APMRP-360")
@features.appsec_request_blocking
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

    @bug(context.library < "java@1.2.0", weblog_variant="spring-boot-openliberty", reason="APPSEC-6583")
    def test_body_value(self):
        """AppSec detects attacks in URL encoded body values"""
        interfaces.library.assert_waf_attack(self.r_value, value='<vmlframe src="xss">', address="server.request.body")


@bug(context.library == "nodejs@2.8.0", reason="APMRP-360")
@features.appsec_request_blocking
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
    @irrelevant(reason="unsupported by framework", library="ruby", weblog_variant="uds-sinatra")
    def test_json_array(self):
        """AppSec detects attacks in JSON body arrays"""
        interfaces.library.assert_waf_attack(self.r_array, value='<vmlframe src="xss">', address="server.request.body")


@bug(context.library == "nodejs@2.8.0", reason="APMRP-360")
@features.appsec_request_blocking
class Test_BodyXml:
    """Appsec supports <XML encoded body>"""

    ATTACK = '<vmlframe src="xss">'
    ENCODED_ATTACK = "&lt;vmlframe src=&quot;xss&quot;&gt;"

    def weblog_post(self, path="/", params=None, data=None, headers=None):
        headers = headers or {}
        headers["Content-Type"] = "application/xml"
        data = f"<?xml version='1.0' encoding='utf-8'?>{data}"
        return weblog.post(path, params=params, data=data, headers=headers)

    def setup_xml_attr_value(self):
        self.r_attr_1 = self.weblog_post("/waf", data='<string attack="var_dump ()" />')
        self.r_attr_2 = self.weblog_post("/waf", data=f'<string attack="{self.ENCODED_ATTACK}" />')

    @bug(
        context.library <= "java@1.39.1" and context.weblog_variant in ("spring-boot-payara", "spring-boot-wildfly"),
        reason="APMRP-360",
    )
    def test_xml_attr_value(self):
        interfaces.library.assert_waf_attack(self.r_attr_1, address="server.request.body", value="var_dump ()")
        interfaces.library.assert_waf_attack(self.r_attr_2, address="server.request.body", value=self.ATTACK)

    def setup_xml_content(self):
        self.r_content_1 = self.weblog_post("/waf", data="<string>var_dump ()</string>")
        self.r_content_2 = self.weblog_post("/waf", data=f"<string>{self.ENCODED_ATTACK}</string>")

    @bug(
        context.library <= "java@1.39.1" and context.weblog_variant in ("spring-boot-payara", "spring-boot-wildfly"),
        reason="APMRP-360",
    )
    def test_xml_content(self):
        interfaces.library.assert_waf_attack(self.r_content_1, address="server.request.body", value="var_dump ()")
        interfaces.library.assert_waf_attack(self.r_content_2, address="server.request.body", value=self.ATTACK)


@features.appsec_request_blocking
class Test_ResponseStatus:
    """Appsec supports values on server.response.status"""

    def setup_basic(self):
        self.r = weblog.get("/mysql")

    @bug(library="java", weblog_variant="spring-boot-openliberty", reason="APPSEC-6583")
    def test_basic(self):
        """AppSec reports 404 responses"""
        interfaces.library.assert_waf_attack(self.r, pattern="404", address="server.response.status")


@features.appsec_request_blocking
class Test_PathParams:
    """Appsec supports values on server.request.path_params"""

    def setup_security_scanner(self):
        self.r = weblog.get("/params/appscan_fingerprint")

    def test_security_scanner(self):
        """AppSec catches attacks in URL path param"""
        interfaces.library.assert_waf_attack(
            self.r, pattern="appscan_fingerprint", address="server.request.path_params"
        )


@features.grpc_threats_management
class Test_gRPC:
    """Appsec supports address grpc.server.request.message"""

    def setup_basic(self):
        self.requests = [
            weblog.grpc("SELECT * FROM products WHERE id=1-SLEEP(15)"),
            weblog.grpc("SELECT * FROM products WHERE id=1; WAITFOR DELAY '00:00:15'"),
        ]

    def test_basic(self):
        """AppSec detects some basic attack"""
        for r in self.requests:
            try:
                interfaces.library.assert_waf_attack(r, address="grpc.server.request.message")
            except Exception as e:
                raise ValueError(f"Basic attack #{self.requests.index(r)} not detected") from e


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2278064284/gRPC+Protocol+Support")
@features.grpc_threats_management
class Test_FullGrpc:
    """Full gRPC support"""

    def test_main(self):
        pytest.fail("Need to write a test")


@scenarios.graphql_appsec
@features.graphql_threats_detection
class Test_GraphQL:
    """GraphQL support"""

    def setup_request_no_attack(self):
        """Set up an innofensive request with no attacks"""

        self.r_no_attack = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": "query getUserByName($name: String) { userByName(name: $name) { id name }}",
                    "variables": {"name": "foo"},
                    "operationName": "getUserByName",
                }
            ),
        )

    def test_request_no_attack(self):
        """Verify that no AppSec event was reported"""

        assert self.r_no_attack.status_code == 200  # There is no attack here!
        interfaces.library.assert_no_appsec_event(self.r_no_attack)

    def base_test_request_monitor_attack(self, resolvers_key_path, all_resolvers_key_path):
        """Verify that the request triggered a directive attack event"""

        assert self.r_attack.status_code == 200  # This attack is never blocking

        failures = []

        try:
            interfaces.library.assert_waf_attack(
                self.r_attack,
                rule="monitor-resolvers",
                key_path=resolvers_key_path,
                value="testattack",
                full_trace=True,
            )
        except ValueError as e:
            failures.append(e)

        try:
            interfaces.library.assert_waf_attack(
                self.r_attack,
                rule="monitor-all-resolvers",
                key_path=all_resolvers_key_path,
                value="testattack",
                full_trace=True,
            )
        except ValueError as e:
            failures.append(e)

        # At least one of the two assertions should have passed...
        if len(failures) >= 2:
            raise ValueError(f"At least one rule should have triggered - {failures[0]}- {failures[1]}")

    def setup_request_monitor_attack(self):
        """Set up a request with a resolver-targeted attack"""

        self.r_attack = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": "query getUserByName($name: String) { userByName(name: $name) { id name }}",
                    "variables": {"name": "testattack"},
                    "operationName": "getUserByName",
                }
            ),
        )

    def test_request_monitor_attack(self):
        self.base_test_request_monitor_attack(["userByName", "name"], ["userByName", "0", "name"])

    def setup_request_monitor_attack_directive(self):
        """Set up a request with a directive-targeted attack"""

        self.r_attack = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": 'query getUserByName($name: String) { userByName(name: $name) @case(format: "testattack") { id name }}',
                    "variables": {"name": "test"},
                    "operationName": "getUserByName",
                }
            ),
        )

    @missing_feature(library="golang", reason="Not supported or implemented in existing libraries")
    def test_request_monitor_attack_directive(self):
        self.base_test_request_monitor_attack(["userByName", "case", "format"], ["userByName", "0", "case", "format"])


@features.grpc_threats_management
@scenarios.appsec_custom_rules
class Test_GrpcServerMethod:
    """Test as a custom rule until we have official rules for the address"""

    def validate_span(self, span, appsec_data):
        tag = "rpc.grpc.full_method"
        if tag not in span["meta"]:
            logger.info(f"Can't find '{tag}' in span's meta")
            return False

        expected = span["meta"][tag]
        value = appsec_data["triggers"][0]["rule_matches"][0]["parameters"][0]["value"]
        if value != expected:
            logger.info(
                f"receive rule match with value '{value}', expected to match span tag '{tag}' with value '{expected}'"
            )
            return False

        return True

    def setup_grpc_server_method_rule(self):
        self.request = weblog.grpc("Mr Bean")

    def test_grpc_server_method_rule(self):
        interfaces.library.assert_waf_attack(
            self.request, address="grpc.server.method", span_validator=self.validate_span
        )

    def setup_streaming_grpc_server_method_rule(self):
        self.request_streaming = weblog.grpc("Mr Stream", streaming=True)

    def test_streaming_grpc_server_method_rule(self):
        interfaces.library.assert_waf_attack(
            self.request_streaming, address="grpc.server.method", span_validator=self.validate_span
        )
