# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
from utils import (
    bug,
    context,
    coverage,
    interfaces,
    irrelevant,
    missing_feature,
    rfc,
    scenarios,
    weblog,
    flaky,
    features,
)


@coverage.basic
@scenarios.appsec_blocking
@features.appsec_request_blocking
class Test_BlockingAddresses:
    """Test the addresses supported for blocking"""

    def setup_block_ip(self):
        self.block_ip_req = weblog.get(headers={"X-Forwarded-For": "1.1.1.1"})

    def test_block_ip(self):
        """can block the request forwarded for the ip"""

        assert self.block_ip_req.status_code == 403

    def setup_block_user(self):
        self.block_user_req = weblog.get("/users", params={"user": "blockedUser"})

    @missing_feature(library="java", reason="Missing /users endpoint")
    @missing_feature(weblog_variant="nextjs", reason="Not supported yet")
    def test_block_user(self):
        """can block the request from the user"""

        assert self.block_user_req.status_code == 403

    def setup_request_method(self):
        self.rm_req = weblog.request("OPTIONS")

    @missing_feature(context.library < "ruby@1.12.0")
    def test_request_method(self):
        """can block on server.request.method"""

        interfaces.library.assert_waf_attack(self.rm_req, rule="tst-037-006")
        assert self.rm_req.status_code == 403

    def setup_request_uri(self):
        self.ruri_req = weblog.get("/waf/foo.git")

    def test_request_uri(self):
        """can block on server.request.uri.raw"""

        interfaces.library.assert_waf_attack(self.ruri_req, rule="tst-037-002")
        assert self.ruri_req.status_code == 403

    def setup_path_params(self):
        self.pp_req = weblog.get("/params/AiKfOeRcvG45")

    @missing_feature(
        context.library < "java@1.15.0",
        reason="When supported, path parameter detection happens on subsequent WAF run",
    )
    @missing_feature(library="nodejs", reason="Not supported yet")
    @missing_feature(
        context.library == "java" and context.weblog_variant == "akka-http",
        reason="path parameters not supported",
    )
    @irrelevant(context.library == "ruby" and context.weblog_variant == "rack")
    @irrelevant(context.library == "golang" and context.weblog_variant == "net-http")
    def test_path_params(self):
        """can block on server.request.path_params"""

        interfaces.library.assert_waf_attack(self.pp_req, rule="tst-037-007")
        assert self.pp_req.status_code == 403

    def setup_request_query(self):
        self.rq_req = weblog.get("/waf", params={"foo": "xtrace"})

    @missing_feature(weblog_variant="nextjs", reason="Not supported yet")
    def test_request_query(self):
        """can block on server.request.query"""

        interfaces.library.assert_waf_attack(self.rq_req, rule="tst-037-001")
        assert self.rq_req.status_code == 403

    def setup_cookies(self):
        self.c_req = weblog.get("/", headers={"Cookie": "mycookie=jdfoSDGFkivRG_234"})

    @missing_feature(context.library < "nodejs@14.16.0", reason="Not supported yet")
    def test_cookies(self):
        """can block on server.request.cookies"""

        interfaces.library.assert_waf_attack(self.c_req, rule="tst-037-008")
        assert self.c_req.status_code == 403

    def setup_request_body_urlencoded(self):
        self.rbue_req = weblog.post("/waf", data={"foo": "bsldhkuqwgervf"})

    @missing_feature(
        context.library < "java@1.15.0", reason="Happens on a subsequent WAF run"
    )
    @missing_feature(weblog_variant="nextjs", reason="Not supported yet")
    @irrelevant(context.library == "golang", reason="Body blocking happens through SDK")
    def test_request_body_urlencoded(self):
        """can block on server.request.body (urlencoded variant)"""

        interfaces.library.assert_waf_attack(self.rbue_req, rule="tst-037-004")
        assert self.rbue_req.status_code == 403

    def setup_request_body_multipart(self):
        self.rbmp_req = weblog.post("/waf", files={"foo": (None, "bsldhkuqwgervf")})

    @missing_feature(context.library == "dotnet", reason="Don't support multipart yet")
    @missing_feature(context.library == "php", reason="Don't support multipart yet")
    @missing_feature(
        context.library < "java@1.15.0", reason="Happens on a subsequent WAF run"
    )
    @missing_feature(library="nodejs", reason="Not supported yet")
    @missing_feature(
        context.weblog_variant
        in (
            "spring-boot-jetty",
            "spring-boot-undertow",
            "spring-boot-openliberty",
            "jersey-grizzly2",
            "resteasy-netty3",
            "ratpack",
        ),
        reason="Blocking on multipart not supported yet",
    )
    @bug(
        context.library == "python" and context.weblog_variant == "django-poc",
        reason="Django bug in multipart body",
    )
    @irrelevant(context.library == "golang", reason="Body blocking happens through SDK")
    def test_request_body_multipart(self):
        """can block on server.request.body (multipart/form-data variant)"""

        interfaces.library.assert_waf_attack(self.rbmp_req, rule="tst-037-004")
        assert self.rbmp_req.status_code == 403

    def setup_response_status(self):
        self.rss_req = weblog.get(path="/status", params={"code": "418"})

    @missing_feature(context.library < "dotnet@2.32.0")
    @missing_feature(
        context.library < "java@1.18.0"
        and context.weblog_variant in ("spring-boot", "uds-spring-boot")
    )
    @missing_feature(
        context.library < "java@1.19.0"
        and context.weblog_variant
        in ("spring-boot-jetty", "spring-boot-undertow", "spring-boot-wildfly")
    )
    @missing_feature(
        context.library == "java"
        and context.weblog_variant
        not in (
            "akka-http",
            "play",
            "spring-boot",
            "uds-spring-boot",
            "spring-boot-jetty",
            "spring-boot-undertow",
            "spring-boot-wildfly",
        )
    )
    @missing_feature(
        context.library == "golang", reason="No blocking on server.response.*"
    )
    @missing_feature(context.library < "ruby@1.10.0")
    @missing_feature(library="nodejs", reason="Not supported yet")
    def test_response_status(self):
        """can block on server.response.status"""

        interfaces.library.assert_waf_attack(self.rss_req, rule="tst-037-005")
        assert self.rss_req.status_code == 403

    def setup_not_found(self):
        self.rnf_req = weblog.get(path="/finger_print")

    @missing_feature(
        context.library == "java"
        and context.weblog_variant not in ("akka-http", "play"),
        reason="Happens on a subsequent WAF run",
    )
    @missing_feature(context.library == "ruby", reason="Not working")
    @missing_feature(library="nodejs", reason="Not supported yet")
    @missing_feature(
        context.library == "golang", reason="No blocking on server.response.*"
    )
    def test_not_found(self):
        """can block on server.response.status"""

        interfaces.library.assert_waf_attack(self.rnf_req, rule="tst-037-010")
        assert self.rnf_req.status_code == 403

    def setup_response_header(self):
        self.rsh_req = weblog.get(path="/headers")

    @missing_feature(context.library < "dotnet@2.32.0")
    @missing_feature(
        context.library == "java"
        and context.weblog_variant not in ("akka-http", "play"),
        reason="Happens on a subsequent WAF run",
    )
    @missing_feature(context.library == "ruby")
    @missing_feature(
        context.library == "php", reason="Headers already sent at this stage"
    )
    @missing_feature(library="nodejs", reason="Not supported yet")
    @missing_feature(
        context.library == "golang", reason="No blocking on server.response.*"
    )
    def test_response_header(self):
        """can block on server.response.headers.no_cookies"""

        interfaces.library.assert_waf_attack(self.rsh_req, rule="tst-037-009")
        assert self.rsh_req.status_code == 403

    @missing_feature(reason="No endpoint defined yet")
    def test_response_cookies(self):
        assert False


def _assert_custom_event_tag_presence(expected_value):
    def wrapper(span):
        tag = "appsec.events.system_tests_appsec_event.value"
        assert tag in span["meta"], f"Can't find {tag} in span's meta"
        value = span["meta"][tag]
        assert value == expected_value
        return True

    return wrapper


def _assert_custom_event_tag_absence():
    def wrapper(span):
        tag = "appsec.events.system_tests_appsec_event.value"
        assert tag not in span["meta"], f"Found {tag} in span's meta"
        return True

    return wrapper


@rfc(
    "https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking"
)
@scenarios.appsec_blocking
@coverage.good
@features.appsec_request_blocking
@bug(
    context.library >= "java@1.20.0"
    and context.weblog_variant == "spring-boot-openliberty"
)
class Test_Blocking_request_method:
    """Test if blocking is supported on server.request.method address"""

    def setup_blocking(self):
        self.rm_req_block = weblog.request("OPTIONS")

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        assert self.rm_req_block.status_code == 403
        interfaces.library.assert_waf_attack(self.rm_req_block, rule="tst-037-006")

    def setup_non_blocking(self):
        self.rm_req_nonblock = weblog.request("GET")

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        assert self.rm_req_nonblock.status_code == 200

    def setup_blocking_before(self):
        self.set_req1 = weblog.request("GET", path="/tag_value/clean_value_3876/200")
        self.block_req2 = weblog.request(
            "OPTIONS", path="/tag_value/tainted_value_6512/200"
        )

    @flaky(context.library < "java@1.16.0")
    def test_blocking_before(self):
        """Test that blocked requests are blocked before being processed"""
        # first request should not block and must set the tag in span accordingly
        assert self.set_req1.status_code == 200
        assert "Value tagged" in self.set_req1.text
        interfaces.library.validate_spans(
            self.set_req1, _assert_custom_event_tag_presence("clean_value_3876")
        )
        # second request should block and must not set the tag in span
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="tst-037-006")
        interfaces.library.validate_spans(
            self.block_req2, _assert_custom_event_tag_absence()
        )


@rfc(
    "https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking"
)
@scenarios.appsec_blocking
@coverage.good
@features.appsec_request_blocking
@bug(
    context.library >= "java@1.20.0"
    and context.weblog_variant == "spring-boot-openliberty"
)
class Test_Blocking_request_uri:
    """Test if blocking is supported on server.request.uri.raw address"""

    def setup_blocking(self):
        self.rm_req_block1 = self.ruri_req = weblog.get("/waf/foo.git")
        # query parameters are part of uri
        self.rm_req_block2 = weblog.get("/waf?foo=.git")

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for response in (self.rm_req_block1, self.rm_req_block2):
            assert response.status_code == 403
            interfaces.library.assert_waf_attack(response, rule="tst-037-002")

    def setup_non_blocking(self):
        self.rm_req_nonblock1 = weblog.get("/waf/legit")

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        assert self.rm_req_nonblock1.status_code == 200

    def setup_test_blocking_uri_raw(self):
        self.rm_req_uri_raw = weblog.get(
            "/waf/uri_raw_should_not_include_scheme_domain_and_port"
        )

    @bug(
        library="dotnet", reason="dotnet may include scheme, domain and port in uri.raw"
    )
    def test_test_blocking_uri_raw(self):
        interfaces.library.assert_waf_attack(self.rm_req_uri_raw, rule="tst-037-011")
        assert self.rm_req_uri_raw.status_code == 403

    def setup_blocking_before(self):
        self.set_req1 = weblog.get("/tag_value/clean_value_3877/200")
        self.block_req2 = weblog.get("/tag_value/tainted_value_6512.git/200")

    def test_blocking_before(self):
        """Test that blocked requests are blocked before being processed"""
        # first request should not block and must set the tag in span accordingly
        assert self.set_req1.status_code == 200
        assert "Value tagged" in self.set_req1.text
        interfaces.library.validate_spans(
            self.set_req1, _assert_custom_event_tag_presence("clean_value_3877")
        )
        # second request should block and must not set the tag in span
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="tst-037-002")
        interfaces.library.validate_spans(
            self.block_req2, _assert_custom_event_tag_absence()
        )


@rfc(
    "https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking"
)
@scenarios.appsec_blocking
@coverage.good
@features.appsec_request_blocking
@bug(
    context.library >= "java@1.20.0"
    and context.weblog_variant == "spring-boot-openliberty"
)
class Test_Blocking_request_path_params:
    """Test if blocking is supported on server.request.path_params address"""

    def setup_blocking(self):
        self.rm_req_block1 = weblog.get("/params/AiKfOeRcvG45")
        self.rm_req_block2 = weblog.get("/waf/AiKfOeRcvG45")

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for response in (self.rm_req_block1, self.rm_req_block2):
            assert response.status_code == 403
            interfaces.library.assert_waf_attack(response, rule="tst-037-007")

    def setup_non_blocking(self):
        # query parameters are not a part of path parameters
        self.rm_req_nonblock = weblog.get("/waf/noharm?value=AiKfOeRcvG45")

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        assert self.rm_req_nonblock.status_code == 200

    def setup_blocking_before(self):
        self.set_req1 = weblog.get("/tag_value/clean_value_3878/200")
        self.block_req2 = weblog.get("/tag_value/tainted_value_AiKfOeRcvG45/200")

    def test_blocking_before(self):
        """Test that blocked requests are blocked before being processed"""
        # first request should not block and must set the tag in span accordingly
        assert self.set_req1.status_code == 200
        assert self.set_req1.text == "Value tagged"
        interfaces.library.validate_spans(
            self.set_req1, _assert_custom_event_tag_presence("clean_value_3878")
        )
        # second request should block and must not set the tag in span
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="tst-037-007")
        interfaces.library.validate_spans(
            self.block_req2, _assert_custom_event_tag_absence()
        )


@rfc(
    "https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking"
)
@scenarios.appsec_blocking
@coverage.good
@features.appsec_request_blocking
@bug(
    context.library >= "java@1.20.0"
    and context.weblog_variant == "spring-boot-openliberty"
)
class Test_Blocking_request_query:
    """Test if blocking is supported on server.request.query address"""

    def setup_blocking(self):
        self.rm_req_block1 = weblog.get("/waf", params={"foo": "xtrace"})
        self.rm_req_block2 = weblog.get("/waf?foo=xtrace")

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for response in (self.rm_req_block1, self.rm_req_block2):
            assert response.status_code == 403
            interfaces.library.assert_waf_attack(response, rule="tst-037-001")

    def setup_non_blocking(self):
        # path parameters are not a part of query parameters
        self.rm_req_nonblock1 = weblog.get("/waf/xtrace")
        # query parameters are blocking only on value not parameter name
        self.rm_req_nonblock2 = weblog.get("/waf?xtrace=foo")

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        for response in (self.rm_req_nonblock1, self.rm_req_nonblock2):
            assert response.status_code == 200

    def setup_blocking_before(self):
        self.set_req1 = weblog.get("/tag_value/clean_value_3879/200")
        self.block_req2 = weblog.get("/tag_value/tainted_value_a1b2c3/200?foo=xtrace")

    def test_blocking_before(self):
        """Test that blocked requests are blocked before being processed"""
        # first request should not block and must set the tag in span accordingly
        assert self.set_req1.status_code == 200
        assert self.set_req1.text == "Value tagged"
        interfaces.library.validate_spans(
            self.set_req1, _assert_custom_event_tag_presence("clean_value_3879")
        )
        # second request should block and must not set the tag in span
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="tst-037-001")
        interfaces.library.validate_spans(
            self.block_req2, _assert_custom_event_tag_absence()
        )


@rfc(
    "https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking"
)
@scenarios.appsec_blocking
@coverage.good
@features.appsec_request_blocking
@bug(
    context.library >= "java@1.20.0"
    and context.weblog_variant == "spring-boot-openliberty"
)
class Test_Blocking_request_headers:
    """Test if blocking is supported on server.request.headers.no_cookies address"""

    def setup_blocking(self):
        self.rm_req_block1 = weblog.get("/waf", headers={"foo": "asldhkuqwgervf"})
        self.rm_req_block2 = weblog.get(
            "/waf", headers={"Accept-Language": "asldhkuqwgervf"}
        )

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for response in (self.rm_req_block1, self.rm_req_block2):
            assert response.status_code == 403
            interfaces.library.assert_waf_attack(response, rule="tst-037-003")

    def setup_non_blocking(self):
        # query parameters are not a part of headers
        self.rm_req_nonblock1 = weblog.get("/waf?value=asldhkuqwgervf")
        # header parameters are blocking only on value not parameter name
        self.rm_req_nonblock2 = weblog.get("/waf", headers={"asldhkuqwgervf": "foo"})

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        for response in (self.rm_req_nonblock1, self.rm_req_nonblock2):
            assert response.status_code == 200

    def setup_blocking_before(self):
        self.set_req1 = weblog.get("/tag_value/clean_value_3880/200")
        self.block_req2 = weblog.get(
            "/tag_value/tainted_value_xyz/200", headers={"foo": "asldhkuqwgervf"}
        )

    def test_blocking_before(self):
        """Test that blocked requests are blocked before being processed"""
        # first request should not block and must set the tag in span accordingly
        assert self.set_req1.status_code == 200
        assert "Value tagged" in self.set_req1.text
        interfaces.library.validate_spans(
            self.set_req1, _assert_custom_event_tag_presence("clean_value_3880")
        )
        # second request should block and must not set the tag in span
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="tst-037-003")
        interfaces.library.validate_spans(
            self.block_req2, _assert_custom_event_tag_absence()
        )


@rfc(
    "https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking"
)
@scenarios.appsec_blocking
@coverage.good
@features.appsec_request_blocking
@bug(
    context.library >= "java@1.20.0"
    and context.weblog_variant == "spring-boot-openliberty"
)
class Test_Blocking_request_cookies:
    """Test if blocking is supported on server.request.cookies address"""

    def setup_blocking(self):
        self.rm_req_block1 = weblog.get("/waf", cookies={"foo": "jdfoSDGFkivRG_234"})
        self.rm_req_block2 = weblog.get(
            "/waf", cookies={"Accept-Language": "jdfoSDGFkivRG_234"}
        )

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for response in (self.rm_req_block1, self.rm_req_block2):
            assert response.status_code == 403
            interfaces.library.assert_waf_attack(response, rule="tst-037-008")

    def setup_non_blocking(self):
        # headers parameters are not a part of cookies
        self.rm_req_nonblock1 = weblog.get("/waf", headers={"foo": "jdfoSDGFkivRG_234"})
        # cookies parameters are blocking only on value not parameter name
        self.rm_req_nonblock2 = weblog.get("/waf", headers={"jdfoSDGFkivRG_234": "foo"})

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        for response in (self.rm_req_nonblock1, self.rm_req_nonblock2):
            assert response.status_code == 200

    def setup_blocking_before(self):
        self.set_req1 = weblog.get("/tag_value/clean_value_3881/200")
        self.block_req2 = weblog.get(
            "/tag_value/tainted_value_cookies/200", cookies={"foo": "jdfoSDGFkivRG_234"}
        )

    def test_blocking_before(self):
        """Test that blocked requests are blocked before being processed"""
        # first request should not block and must set the tag in span accordingly
        assert self.set_req1.status_code == 200
        assert self.set_req1.text == "Value tagged"
        interfaces.library.validate_spans(
            self.set_req1, _assert_custom_event_tag_presence("clean_value_3881")
        )
        # second request should block and must not set the tag in span
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="tst-037-008")
        interfaces.library.validate_spans(
            self.block_req2, _assert_custom_event_tag_absence()
        )


@rfc(
    "https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking"
)
@scenarios.appsec_blocking
@coverage.good
@features.appsec_request_blocking
@bug(
    context.library >= "java@1.20.0"
    and context.weblog_variant == "spring-boot-openliberty"
)
class Test_Blocking_request_body:
    """Test if blocking is supported on server.request.body address for urlencoded body"""

    def setup_blocking(self):
        self.rm_req_block1 = weblog.post("/waf", data={"value1": "bsldhkuqwgervf"})
        self.rm_req_block2 = weblog.post("/waf", data={"foo": "bsldhkuqwgervf"})

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for response in (self.rm_req_block1, self.rm_req_block2):
            assert response.status_code == 403
            interfaces.library.assert_waf_attack(response, rule="tst-037-004")

    def setup_non_blocking(self):
        # raw body are never parsed
        self.rm_req_nonblock1 = weblog.post(
            "/waf",
            data=b'\x00{"value3": "bsldhkuqwgervf"}\xFF',
            headers={"content-type": "application/octet-stream"},
        )
        self.rm_req_nonblock2 = weblog.post("/waf", data={"good": "value"})

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        assert self.rm_req_nonblock1.status_code == 200
        assert self.rm_req_nonblock2.status_code == 200

    def setup_non_blocking_plain_text(self):
        self.rm_req_nonblock_plain_text = weblog.post(
            "/waf",
            data=b'{"value4": "bsldhkuqwgervf"}',
            headers={"content-type": "text/plain"},
        )

    @irrelevant(
        context.weblog_variant
        in ("akka-http", "play", "jersey-grizzly2", "resteasy-netty3"),
        reason="Blocks on text/plain if parsed to a String",
    )
    def test_non_blocking_plain_text(self):
        # TODO: This test is pending a better definition of when text/plain is considered parsed body,
        # which depends on application logic.
        assert self.rm_req_nonblock_plain_text.status_code == 200

    def setup_blocking_before(self):
        self.set_req1 = weblog.post(
            "/tag_value/clean_value_3882/200", data={"good": "value"}
        )
        self.block_req2 = weblog.post(
            "/tag_value/tainted_value_body/200", data={"value5": "bsldhkuqwgervf"}
        )

    def test_blocking_before(self):
        """Test that blocked requests are blocked before being processed"""
        # first request should not block and must set the tag in span accordingly
        assert self.set_req1.status_code == 200
        assert self.set_req1.text == "Value tagged"
        interfaces.library.validate_spans(
            self.set_req1, _assert_custom_event_tag_presence("clean_value_3882")
        )
        # second request should block and must not set the tag in span
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="tst-037-004")
        interfaces.library.validate_spans(
            self.block_req2, _assert_custom_event_tag_absence()
        )


@rfc(
    "https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking"
)
@scenarios.appsec_blocking
@coverage.good
@features.appsec_response_blocking
class Test_Blocking_response_status:
    """Test if blocking is supported on server.response.status address"""

    def setup_blocking(self):
        self.rm_req_block = {
            status: weblog.get(f"/tag_value/anything/{status}")
            for status in (415, 416, 417, 418)
        }

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for code, response in self.rm_req_block.items():
            assert response.status_code == 403, response.request.url
            interfaces.library.assert_waf_attack(response, rule="tst-037-005")

    def setup_non_blocking(self):
        self.rm_req_nonblock = {
            status: weblog.get(f"/tag_value/anything/{status}")
            for status in (411, 412, 413, 414)
        }

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        for code, response in self.rm_req_nonblock.items():
            assert response.status_code == code, response.request.url


@rfc(
    "https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking"
)
@scenarios.appsec_blocking
@coverage.good
@features.appsec_response_blocking
class Test_Blocking_response_headers:
    """Test if blocking is supported on server.response.headers.no_cookies address"""

    def setup_blocking(self):
        self.rm_req_block1 = weblog.get(
            f"/tag_value/anything/200?content-language=en-us"
        )
        self.rm_req_block2 = weblog.get(
            f"/tag_value/anything/200?content-language=krypton"
        )

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for response in (self.rm_req_block1, self.rm_req_block2):
            assert response.status_code == 403, response.request.url
            interfaces.library.assert_waf_attack(response, rule="tst-037-009")

    def setup_non_blocking(self):
        self.rm_req_nonblock1 = weblog.get(
            f"/tag_value/anything/200?content-color=en-us"
        )
        self.rm_req_nonblock2 = weblog.get(
            f"/tag_value/anything/200?content-language=fr"
        )

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        for response in (self.rm_req_nonblock1, self.rm_req_nonblock2):
            assert response.status_code == 200


@rfc(
    "https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking"
)
@features.appsec_request_blocking
class Test_Suspicious_Request_Blocking:
    """Test if blocking on multiple addresses with multiple rules is supported"""

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        assert False, "TODO"

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        assert False, "TODO"

    def test_blocking_before(self):
        """Test that blocked requests are blocked before being processed"""
        assert False, "TODO"


@scenarios.appsec_blocking
@coverage.good
@features.appsec_request_blocking
class Test_BlockingGraphqlResolvers:
    """Test if blocking is supported on graphql.server.all_resolvers address"""

    def setup_request_non_blocking(self):
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

    def test_request_non_blocking(self):
        assert self.r_no_attack.status_code == 200
        for _, span in interfaces.library.get_root_spans(request=self.r_no_attack):
            meta = span.get("meta", {})
            assert "_dd.appsec.event" not in meta
            assert "_dd.appsec.json" not in meta

    def setup_request_monitor_attack(self):
        """ Currently only monitoring is implemented"""

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
        assert self.r_attack.status_code == 200
        for _, span in interfaces.library.get_root_spans(request=self.r_attack):
            meta = span.get("meta", {})
            assert meta["appsec.event"] == "true"
            assert "_dd.appsec.json" in meta
            rule_triggered = json.loads(meta["_dd.appsec.json"])["triggers"][0]
            assert rule_triggered["rule"]["id"] == "monitor-resolvers"
            parameters = rule_triggered["rule_matches"][0]["parameters"][0]
            assert parameters["address"] == "graphql.server.all_resolvers"
            assert parameters["key_path"] == ["userByName", "0", "name"]
            assert parameters["value"] == "testattack"
