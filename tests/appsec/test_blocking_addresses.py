# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
from utils import (
    bug,
    context,
    interfaces,
    irrelevant,
    missing_feature,
    rfc,
    scenarios,
    weblog,
    flaky,
    features,
)


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


@scenarios.appsec_blocking
@features.appsec_request_blocking
class Test_Blocking_client_ip:
    """Test if blocking is supported on http.client_ip address"""

    def setup_blocking(self):
        self.rm_req_block = weblog.get(headers={"X-Forwarded-For": "1.1.1.1"})

    def test_blocking(self):
        """can block the request forwarded for the ip"""

        assert self.rm_req_block.status_code == 403
        interfaces.library.assert_waf_attack(self.rm_req_block, rule="blk-001-001")

    def setup_blocking_before(self):
        self.block_req2 = weblog.get("/tag_value/tainted_value_6512/200", headers={"X-Forwarded-For": "1.1.1.1"})

    @bug(weblog_variant="spring-boot-openliberty", reason="tag present")
    def test_blocking_before(self):
        """Test that blocked requests are blocked before being processed"""
        # second request should block and must not set the tag in span
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="blk-001-001")
        interfaces.library.validate_spans(self.block_req2, _assert_custom_event_tag_absence())


@scenarios.appsec_blocking
@features.appsec_request_blocking
class Test_Blocking_user_id:
    """Test if blocking is supported on usr.id address"""

    def setup_block_user(self):
        self.rm_req_block = weblog.get("/users", params={"user": "blockedUser"})

    def test_block_user(self):
        """can block the request from the user"""

        assert self.rm_req_block.status_code == 403
        interfaces.library.assert_waf_attack(self.rm_req_block, rule="block-users")


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking")
@scenarios.appsec_blocking
@features.appsec_request_blocking
@bug(context.library >= "java@1.20.0" and context.weblog_variant == "spring-boot-openliberty")
class Test_Blocking_request_method:
    """Test if blocking is supported on server.request.method address"""

    def setup_blocking(self):
        if not hasattr(self, "rm_req_block") or self.rm_req_block is None:
            self.rm_req_block = weblog.request("OPTIONS")

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        assert self.rm_req_block.status_code == 403
        interfaces.library.assert_waf_attack(self.rm_req_block, rule="tst-037-006")

    def setup_non_blocking(self):
        self.setup_blocking()
        self.rm_req_nonblock = weblog.request("GET")

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        self.test_blocking()
        assert self.rm_req_nonblock.status_code == 200

    def setup_blocking_before(self):
        self.set_req1 = weblog.request("GET", path="/tag_value/clean_value_3876/200")
        self.block_req2 = weblog.request("OPTIONS", path="/tag_value/tainted_value_6512/200")

    @flaky(context.library < "java@1.16.0")
    def test_blocking_before(self):
        """Test that blocked requests are blocked before being processed"""
        # first request should not block and must set the tag in span accordingly
        assert self.set_req1.status_code == 200
        assert "Value tagged" in self.set_req1.text
        interfaces.library.validate_spans(self.set_req1, _assert_custom_event_tag_presence("clean_value_3876"))
        # second request should block and must not set the tag in span
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="tst-037-006")
        interfaces.library.validate_spans(self.block_req2, _assert_custom_event_tag_absence())


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking")
@scenarios.appsec_blocking
@features.appsec_request_blocking
@bug(context.library >= "java@1.20.0" and context.weblog_variant == "spring-boot-openliberty")
class Test_Blocking_request_uri:
    """Test if blocking is supported on server.request.uri.raw address"""

    def setup_blocking(self):
        if not hasattr(self, "rm_req_block1") or self.rm_req_block1 is None:
            self.rm_req_block1 = self.ruri_req = weblog.get("/waf/foo.git")
        # query parameters are part of uri
        if not hasattr(self, "rm_req_block2") or self.rm_req_block2 is None:
            self.rm_req_block2 = weblog.get("/waf?foo=.git")

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for response in (self.rm_req_block1, self.rm_req_block2):
            assert response.status_code == 403
            interfaces.library.assert_waf_attack(response, rule="tst-037-002")

    def setup_non_blocking(self):
        self.setup_blocking()
        self.rm_req_nonblock1 = weblog.get("/waf/legit")

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        self.test_blocking()
        assert self.rm_req_nonblock1.status_code == 200

    def setup_blocking_uri_raw(self):
        self.rm_req_uri_raw = weblog.get("/waf/uri_raw_should_not_include_scheme_domain_and_port")

    @bug(context.library < "dotnet@2.50.0", reason="dotnet may include scheme, domain and port in uri.raw")
    def test_blocking_uri_raw(self):
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
        interfaces.library.validate_spans(self.set_req1, _assert_custom_event_tag_presence("clean_value_3877"))
        # second request should block and must not set the tag in span
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="tst-037-002")
        interfaces.library.validate_spans(self.block_req2, _assert_custom_event_tag_absence())


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking")
@scenarios.appsec_blocking
@features.appsec_request_blocking
@bug(context.library >= "java@1.20.0" and context.weblog_variant == "spring-boot-openliberty")
class Test_Blocking_request_path_params:
    """Test if blocking is supported on server.request.path_params address"""

    def setup_blocking(self):
        if not hasattr(self, "rm_req_block1") or self.rm_req_block1 is None:
            self.rm_req_block1 = weblog.get("/params/AiKfOeRcvG45")
        if not hasattr(self, "rm_req_block2") or self.rm_req_block2 is None:
            self.rm_req_block2 = weblog.get("/waf/AiKfOeRcvG45")

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for response in (self.rm_req_block1, self.rm_req_block2):
            assert response.status_code == 403
            interfaces.library.assert_waf_attack(response, rule="tst-037-007")

    def setup_non_blocking(self):
        self.setup_blocking()
        # query parameters are not a part of path parameters
        self.rm_req_nonblock = weblog.get("/waf/noharm?value=AiKfOeRcvG45")

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        self.test_blocking()
        assert self.rm_req_nonblock.status_code == 200

    def setup_blocking_before(self):
        self.set_req1 = weblog.get("/tag_value/clean_value_3878/200")
        self.block_req2 = weblog.get("/tag_value/tainted_value_AiKfOeRcvG45/200")

    def test_blocking_before(self):
        """Test that blocked requests are blocked before being processed"""
        # first request should not block and must set the tag in span accordingly
        assert self.set_req1.status_code == 200
        assert self.set_req1.text == "Value tagged"
        interfaces.library.validate_spans(self.set_req1, _assert_custom_event_tag_presence("clean_value_3878"))
        # second request should block and must not set the tag in span
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="tst-037-007")
        interfaces.library.validate_spans(self.block_req2, _assert_custom_event_tag_absence())


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking")
@scenarios.appsec_blocking
@features.appsec_request_blocking
@bug(context.library >= "java@1.20.0" and context.weblog_variant == "spring-boot-openliberty")
class Test_Blocking_request_query:
    """Test if blocking is supported on server.request.query address"""

    def setup_blocking(self):
        if not hasattr(self, "rm_req_block1") or self.rm_req_block1 is None:
            self.rm_req_block1 = weblog.get("/waf", params={"foo": "xtrace"})
        if not hasattr(self, "rm_req_block2") or self.rm_req_block2 is None:
            self.rm_req_block2 = weblog.get("/waf?foo=xtrace")

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for response in (self.rm_req_block1, self.rm_req_block2):
            assert response.status_code == 403
            interfaces.library.assert_waf_attack(response, rule="tst-037-001")

    def setup_non_blocking(self):
        self.setup_blocking()
        # path parameters are not a part of query parameters
        self.rm_req_nonblock1 = weblog.get("/waf/xtrace")
        # query parameters are blocking only on value not parameter name
        self.rm_req_nonblock2 = weblog.get("/waf?xtrace=foo")

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        self.test_blocking()
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
        interfaces.library.validate_spans(self.set_req1, _assert_custom_event_tag_presence("clean_value_3879"))
        # second request should block and must not set the tag in span
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="tst-037-001")
        interfaces.library.validate_spans(self.block_req2, _assert_custom_event_tag_absence())


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking")
@scenarios.appsec_blocking
@features.appsec_request_blocking
@bug(context.library >= "java@1.20.0" and context.weblog_variant == "spring-boot-openliberty")
class Test_Blocking_request_headers:
    """Test if blocking is supported on server.request.headers.no_cookies address"""

    def setup_blocking(self):
        if not hasattr(self, "rm_req_block1") or self.rm_req_block1 is None:
            self.rm_req_block1 = weblog.get("/waf", headers={"foo": "asldhkuqwgervf"})
        if not hasattr(self, "rm_req_block2") or self.rm_req_block2 is None:
            self.rm_req_block2 = weblog.get("/waf", headers={"Accept-Language": "asldhkuqwgervf"})

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for response in (self.rm_req_block1, self.rm_req_block2):
            assert response.status_code == 403
            interfaces.library.assert_waf_attack(response, rule="tst-037-003")

    def setup_non_blocking(self):
        self.setup_blocking()
        # query parameters are not a part of headers
        self.rm_req_nonblock1 = weblog.get("/waf?value=asldhkuqwgervf")
        # header parameters are blocking only on value not parameter name
        self.rm_req_nonblock2 = weblog.get("/waf", headers={"asldhkuqwgervf": "foo"})

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        self.test_blocking()
        for response in (self.rm_req_nonblock1, self.rm_req_nonblock2):
            assert response.status_code == 200

    def setup_blocking_before(self):
        self.set_req1 = weblog.get("/tag_value/clean_value_3880/200")
        self.block_req2 = weblog.get("/tag_value/tainted_value_xyz/200", headers={"foo": "asldhkuqwgervf"})

    def test_blocking_before(self):
        """Test that blocked requests are blocked before being processed"""
        # first request should not block and must set the tag in span accordingly
        assert self.set_req1.status_code == 200
        assert "Value tagged" in self.set_req1.text
        interfaces.library.validate_spans(self.set_req1, _assert_custom_event_tag_presence("clean_value_3880"))
        # second request should block and must not set the tag in span
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="tst-037-003")
        interfaces.library.validate_spans(self.block_req2, _assert_custom_event_tag_absence())


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking")
@scenarios.appsec_blocking
@features.appsec_request_blocking
@bug(context.library >= "java@1.20.0" and context.weblog_variant == "spring-boot-openliberty")
class Test_Blocking_request_cookies:
    """Test if blocking is supported on server.request.cookies address"""

    def setup_blocking(self):
        if not hasattr(self, "rm_req_block1") or self.rm_req_block1 is None:
            self.rm_req_block1 = weblog.get("/waf", cookies={"foo": "jdfoSDGFkivRG_234"})
        if not hasattr(self, "rm_req_block2") or self.rm_req_block2 is None:
            self.rm_req_block2 = weblog.get("/waf", cookies={"Accept-Language": "jdfoSDGFkivRG_234"})

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for response in (self.rm_req_block1, self.rm_req_block2):
            assert response.status_code == 403
            interfaces.library.assert_waf_attack(response, rule="tst-037-008")

    def setup_non_blocking(self):
        self.setup_blocking()
        # headers parameters are not a part of cookies
        self.rm_req_nonblock1 = weblog.get("/waf", headers={"foo": "jdfoSDGFkivRG_234"})
        # cookies parameters are blocking only on value not parameter name
        self.rm_req_nonblock2 = weblog.get("/waf", headers={"jdfoSDGFkivRG_234": "foo"})

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        self.test_blocking()
        for response in (self.rm_req_nonblock1, self.rm_req_nonblock2):
            assert response.status_code == 200

    def setup_blocking_before(self):
        self.set_req1 = weblog.get("/tag_value/clean_value_3881/200")
        self.block_req2 = weblog.get("/tag_value/tainted_value_cookies/200", cookies={"foo": "jdfoSDGFkivRG_234"})

    def test_blocking_before(self):
        """Test that blocked requests are blocked before being processed"""
        # first request should not block and must set the tag in span accordingly
        assert self.set_req1.status_code == 200
        assert self.set_req1.text == "Value tagged"
        interfaces.library.validate_spans(self.set_req1, _assert_custom_event_tag_presence("clean_value_3881"))
        # second request should block and must not set the tag in span
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="tst-037-008")
        interfaces.library.validate_spans(self.block_req2, _assert_custom_event_tag_absence())


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking")
@scenarios.appsec_blocking
@features.appsec_request_blocking
@bug(context.library >= "java@1.20.0" and context.weblog_variant == "spring-boot-openliberty")
class Test_Blocking_request_body:
    """Test if blocking is supported on server.request.body address for urlencoded body"""

    def setup_blocking(self):
        if not hasattr(self, "rm_req_block1") or self.rm_req_block1 is None:
            self.rm_req_block1 = weblog.post("/waf", data={"value1": "bsldhkuqwgervf"})
        if not hasattr(self, "rm_req_block2") or self.rm_req_block2 is None:
            self.rm_req_block2 = weblog.post("/waf", data={"foo": "bsldhkuqwgervf"})

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for response in (self.rm_req_block1, self.rm_req_block2):
            assert response.status_code == 403
            interfaces.library.assert_waf_attack(response, rule="tst-037-004")

    def setup_non_blocking(self):
        self.setup_blocking()
        # raw body are never parsed
        self.rm_req_nonblock1 = weblog.post(
            "/waf", data=b'\x00{"value3": "bsldhkuqwgervf"}\xFF', headers={"content-type": "application/octet-stream"}
        )
        self.rm_req_nonblock2 = weblog.post("/waf", data={"good": "value"})

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        self.test_blocking()
        assert self.rm_req_nonblock1.status_code == 200
        assert self.rm_req_nonblock2.status_code == 200

    def setup_non_blocking_plain_text(self):
        self.setup_blocking()
        self.rm_req_nonblock_plain_text = weblog.post(
            "/waf", data=b'{"value4": "bsldhkuqwgervf"}', headers={"content-type": "text/plain"}
        )

    @irrelevant(
        context.weblog_variant in ("akka-http", "play", "jersey-grizzly2", "resteasy-netty3"),
        reason="Blocks on text/plain if parsed to a String",
    )
    def test_non_blocking_plain_text(self):
        self.test_blocking()
        # TODO: This test is pending a better definition of when text/plain is considered parsed body,
        # which depends on application logic.
        assert self.rm_req_nonblock_plain_text.status_code == 200

    def setup_blocking_before(self):
        self.set_req1 = weblog.post("/tag_value/clean_value_3882/200", data={"good": "value"})
        self.block_req2 = weblog.post("/tag_value/tainted_value_body/200", data={"value5": "bsldhkuqwgervf"})

    def test_blocking_before(self):
        """Test that blocked requests are blocked before being processed"""
        # first request should not block and must set the tag in span accordingly
        assert self.set_req1.status_code == 200
        assert self.set_req1.text == "Value tagged"
        interfaces.library.validate_spans(self.set_req1, _assert_custom_event_tag_presence("clean_value_3882"))
        # second request should block and must not set the tag in span
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="tst-037-004")
        interfaces.library.validate_spans(self.block_req2, _assert_custom_event_tag_absence())


@scenarios.appsec_blocking
@features.appsec_request_blocking
class Test_Blocking_request_body_multipart:
    """Test if blocking is supported on server.request.body address for multipart body"""

    def setup_blocking(self):
        self.rbmp_req = weblog.post("/waf", files={"foo": (None, "bsldhkuqwgervf")})

    def test_blocking(self):
        """can block on server.request.body (multipart/form-data variant)"""

        interfaces.library.assert_waf_attack(self.rbmp_req, rule="tst-037-004")
        assert self.rbmp_req.status_code == 403


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking")
@scenarios.appsec_blocking
@features.appsec_response_blocking
class Test_Blocking_response_status:
    """Test if blocking is supported on server.response.status address"""

    def setup_blocking(self):
        if not hasattr(self, "rm_req_block") or self.rm_req_block is None:
            self.rm_req_block = {status: weblog.get(f"/tag_value/anything/{status}") for status in (415, 416, 417, 418)}

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for response in self.rm_req_block.values():
            assert response.status_code == 403, response.request.url
            interfaces.library.assert_waf_attack(response, rule="tst-037-005")

    def setup_non_blocking(self):
        self.setup_blocking()
        self.rm_req_nonblock = {
            str(status): weblog.get(f"/tag_value/anything/{status}") for status in (411, 412, 413, 414)
        }

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        self.test_blocking()
        for code, response in self.rm_req_nonblock.items():
            assert str(response.status_code) == code, response.request.url

    def setup_not_found(self):
        self.rnf_req = weblog.get(path="/finger_print")

    @missing_feature(
        context.library == "java" and context.weblog_variant not in ("akka-http", "play"),
        reason="Happens on a subsequent WAF run",
    )
    @missing_feature(context.library == "ruby", reason="Not working")
    @missing_feature(context.library == "golang", reason="No blocking on server.response.*")
    def test_not_found(self):
        """can block on server.response.status"""

        interfaces.library.assert_waf_attack(self.rnf_req, rule="tst-037-010")
        assert self.rnf_req.status_code == 403


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking")
@scenarios.appsec_blocking
@features.appsec_response_blocking
class Test_Blocking_response_headers:
    """Test if blocking is supported on server.response.headers.no_cookies address"""

    def setup_blocking(self):
        if not hasattr(self, "rm_req_block1") or self.rm_req_block1 is None:
            self.rm_req_block1 = weblog.get(f"/tag_value/anything/200?content-language=fo-fo")
        if not hasattr(self, "rm_req_block2") or self.rm_req_block2 is None:
            self.rm_req_block2 = weblog.get(f"/tag_value/anything/200?content-language=krypton")

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        for response in (self.rm_req_block1, self.rm_req_block2):
            assert response.status_code == 403, response.request.url
            interfaces.library.assert_waf_attack(response, rule="tst-037-009")

    def setup_non_blocking(self):
        self.setup_blocking()
        self.rm_req_nonblock1 = weblog.get(f"/tag_value/anything/200?content-color=fo-fo")
        self.rm_req_nonblock2 = weblog.get(f"/tag_value/anything/200?content-language=fr")

    def test_non_blocking(self):
        """Test if requests that should not be blocked are not blocked"""
        self.test_blocking()
        for response in (self.rm_req_nonblock1, self.rm_req_nonblock2):
            assert response.status_code == 200


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking")
@scenarios.appsec_blocking
@features.appsec_request_blocking
class Test_Suspicious_Request_Blocking:
    """Test if blocking on multiple addresses with multiple rules is supported"""

    def setup_blocking(self):
        self.rm_req_block = weblog.get(
            f"/tag_value/cGDgSRJvklxGOKMTNfQMViBPpKAvpFoc_ypMrmzrWATkLrPKLblvpRGGltBSgHWrK/200?attack=SAGihOkuSwXXFDXNqAWJzNuZEdKNunrJ",
            cookies={"foo": "PwXuEQEdeAjzWpCDqAzPqiUAdXJMHwtS"},
            headers={"content-type": "text/plain", "client": "kCgvxrYeiwUSYkAuniuGktdvzXYEPSff"},
        )

    def test_blocking(self):
        """Test if requests that should be blocked are blocked"""
        assert self.rm_req_block.status_code == 403, self.rm_req_block.request.url
        interfaces.library.assert_waf_attack(self.rm_req_block, rule="tst-037-012")

    def setup_blocking_before(self):
        self.set_req1 = weblog.post(
            "/tag_value/clean_value_3882/200?attack=SAGihOkuSwXXFDXNqAWJzNuZEdKNunrJ",
            data={"good": "value"},
            cookies={"foo": "PwXuEQEdeAjzWpCDqAzPqiUAdXJMHwtS"},
        )
        self.block_req2 = weblog.get(
            f"/tag_value/cGDgSRJvklxGOKMTNfQMViBPpKAvpFoc_ypMrmzrWATkLrPKLblvpRGGltBSgHWrK/200?attack=SAGihOkuSwXXFDXNqAWJzNuZEdKNunrJ",
            cookies={"foo": "PwXuEQEdeAjzWpCDqAzPqiUAdXJMHwtS"},
            headers={"content-type": "text/plain", "client": "kCgvxrYeiwUSYkAuniuGktdvzXYEPSff"},
        )

    def test_blocking_before(self):
        """Test that blocked requests are blocked before being processed"""
        # first request should not block and must set the tag in span accordingly
        assert self.set_req1.status_code == 200
        assert self.set_req1.text == "Value tagged"
        interfaces.library.validate_spans(self.set_req1, _assert_custom_event_tag_presence("clean_value_3882"))
        """Test that blocked requests are blocked before being processed"""
        assert self.block_req2.status_code == 403
        interfaces.library.assert_waf_attack(self.block_req2, rule="tst-037-012")
        interfaces.library.validate_spans(self.block_req2, _assert_custom_event_tag_absence())


@scenarios.graphql_appsec
@features.appsec_request_blocking
class Test_BlockingGraphqlResolvers:
    """Test if blocking is supported on graphql.server.all_resolvers address"""

    def setup_request_block_attack(self):
        """Currently only monitoring is implemented"""

        self.r_attack = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": "query getUserByName($name: String) { userByName(name: $name) { id name }}",
                    "variables": {"name": "testblockresolver"},
                    "operationName": "getUserByName",
                }
            ),
        )

    def test_request_block_attack(self):
        assert self.r_attack.status_code == 403
        for _, span in interfaces.library.get_root_spans(request=self.r_attack):
            meta = span.get("meta", {})
            meta_struct = span.get("meta_struct", {})
            assert meta["appsec.event"] == "true"
            assert ("_dd.appsec.json" in meta) ^ ("appsec" in meta_struct)
            appsec = meta.get("_dd.appsec.json", {}) or meta_struct.get("appsec", {})
            rule_triggered = appsec["triggers"][0]
            parameters = rule_triggered["rule_matches"][0]["parameters"][0]
            assert (
                parameters["address"] == "graphql.server.all_resolvers"
                or parameters["address"] == "graphql.server.resolver"
            )
            assert rule_triggered["rule"]["id"] == (
                "block-resolvers" if parameters["address"] == "graphql.server.resolver" else "block-all-resolvers"
            )
            assert parameters["key_path"] == (
                ["userByName", "name"]
                if parameters["address"] == "graphql.server.resolver"
                else ["userByName", "0", "name"]
            )
            assert parameters["value"] == "testblockresolver"

    def setup_request_block_attack_directive(self):
        """Currently only monitoring is implemented"""

        self.r_attack = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": 'query getUserByName($name: String) { userByName(name: $name) @case(format: "testblockresolver") { id name }}',
                    "variables": {"name": "test"},
                    "operationName": "getUserByName",
                }
            ),
        )

    def test_request_block_attack_directive(self):
        assert self.r_attack.status_code == 403
        for _, span in interfaces.library.get_root_spans(request=self.r_attack):
            meta = span.get("meta", {})
            meta_struct = span.get("meta_struct", {})
            assert meta["appsec.event"] == "true"
            assert ("_dd.appsec.json" in meta) ^ ("appsec" in meta_struct)
            appsec = meta.get("_dd.appsec.json", {}) or meta_struct.get("appsec", {})
            rule_triggered = appsec["triggers"][0]
            assert rule_triggered["rule"]["id"] == "block-resolvers"
            parameters = rule_triggered["rule_matches"][0]["parameters"][0]
            assert (
                parameters["address"] == "graphql.server.all_resolvers"
                or parameters["address"] == "graphql.server.resolver"
            )
            assert (
                parameters["key_path"] == ["userByName", "case", "format"]
                if parameters["address"] == "graphql.server.resolver"
                else ["userByName", "0", "case", "format"]
            )
            assert parameters["value"] == "testblockresolver"
