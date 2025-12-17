# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import bug, context, interfaces, irrelevant, missing_feature, rfc, weblog, features, scenarios
from utils._weblog import HttpResponse


@features.envoy_external_processing
@features.haproxy_stream_processing_offload
@features.security_events_metadata
@scenarios.external_processing
@scenarios.stream_processing_offload
@scenarios.default
class Test_StandardTagsMethod:
    """Tests to verify that libraries annotate spans with correct http.method tags"""

    def setup_methods(self):
        verbs = ["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
        self.requests = {}

        for verb in verbs:
            data = "notmuchofabody" if verb in ("POST", "PUT") else None
            self.requests[verb] = weblog.request(verb, "/waf", data=data)

    def test_methods(self):
        for verb, request in self.requests.items():
            interfaces.library.add_span_tag_validation(request=request, tags={"http.method": verb})

    def setup_method_trace(self):
        self.trace_request = weblog.trace("/waf", data=None)

    @irrelevant(library="php", reason="Trace method does not reach php-land")
    @missing_feature(weblog_variant="spring-boot-payara", reason="This weblog variant is currently not accepting TRACE")
    def test_method_trace(self):
        interfaces.library.add_span_tag_validation(request=self.trace_request, tags={"http.method": "TRACE"})


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2490990623/QueryString+-+Sensitive+Data+Obfuscation")
@features.envoy_external_processing
@features.haproxy_stream_processing_offload
@scenarios.external_processing
@scenarios.stream_processing_offload
@scenarios.default
# Tests for verifying behavior when query string obfuscation is configured can be found in the Test_Config_ObfuscationQueryStringRegexp test classes
class Test_StandardTagsUrl:
    """Tests to verify that libraries annotate spans with correct http.url tags"""

    def setup_url_basic(self):
        self.basic_request = weblog.get("/waf")

    def test_url_basic(self):
        interfaces.library.add_span_tag_validation(
            self.basic_request, tags={"http.url": r"^.*/waf$"}, value_as_regular_expression=True
        )

    def setup_url_with_query_string(self):
        self.r_with_query_string = weblog.get("/waf?key1=val1&key2=val2&key3=val3")

    def test_url_with_query_string(self):
        interfaces.library.add_span_tag_validation(
            self.r_with_query_string,
            tags={"http.url": r"^.*/waf\?key1=val1&key2=val2&key3=val3$"},
            value_as_regular_expression=True,
        )

    def setup_url_with_sensitive_query_string_legacy(self):
        # pylint: disable=line-too-long
        self.requests_sensitive_query_string = [
            (
                weblog.get("/waf?pass=03cb9f67-dbbc-4cb8-b966-329951e10934&key2=val2&key3=val3"),
                r"^.*/waf\?<redacted>&key2=val2&key3=val3$",
            ),
            (
                weblog.get("/waf?key1=val1&public_key=MDNjYjlmNjctZGJiYy00Y2I4LWI5NjYtMzI5OTUxZTEwOTM0&key3=val3"),
                r"^.*/waf\?key1=val1&<redacted>&key3=val3$",
            ),
            (
                weblog.get("/waf?key1=val1&key2=val2&token=03cb9f67dbbc4cb8b966329951e10934"),
                r"^.*/waf\?key1=val1&key2=val2&<redacted>$",
            ),
            (
                weblog.get(
                    "/waf?json=%7B%20%22sign%22%3A%20%22%7B0x03cb9f67%2C0xdbbc%2C0x4cb8%2C%7B0xb9%2C0x66%2C0x32%2C0x99%2C0x51%2C0xe1%2C0x09%2C0x34%7D%7D%22%7D"
                ),
                r"^.*/waf\?json=%7B%20%22<redacted>%7D$",
            ),
        ]

    # when tracer is updated, add (for example)
    @irrelevant(context.library >= "java@1.21.0", reason="java released the new version at 1.21.0")
    @irrelevant(context.library >= "python@1.18.0rc1", reason="python released the new version at 1.19.0")
    @irrelevant(context.library >= "dotnet@2.41", reason="dotnet released the new version at 2.41.0")
    @irrelevant(context.library >= "php@0.93.0", reason="php released the new version at 0.93.0")
    def test_url_with_sensitive_query_string_legacy(self):
        for r, tag in self.requests_sensitive_query_string:
            interfaces.library.add_span_tag_validation(
                request=r, tags={"http.url": tag}, value_as_regular_expression=True
            )

    def setup_url_with_sensitive_query_string(self):
        # pylint: disable=line-too-long
        self.requests_sensitive_query_string = [
            (
                weblog.get("/waf?pass=03cb9f67-dbbc-4cb8-b966-329951e10934&key2=val2&key3=val3"),
                r"^.*/waf\?<redacted>&key2=val2&key3=val3$",
            ),
            (
                weblog.get("/waf?key1=val1&public_key=MDNjYjlmNjctZGJiYy00Y2I4LWI5NjYtMzI5OTUxZTEwOTM0&key3=val3"),
                r"^.*/waf\?key1=val1&<redacted>&key3=val3$",
            ),
            (
                weblog.get("/waf?key1=val1&key2=val2&token=03cb9f67dbbc4cb8b966329951e10934"),
                r"^.*/waf\?key1=val1&key2=val2&<redacted>$",
            ),
            (weblog.get("/waf?key1=val1&key2=val2&application_key=123"), r"^.*/waf\?key1=val1&key2=val2&<redacted>$"),
            (
                weblog.get(
                    "/waf?json=%7B%20%22sign%22%3A%20%22%7B0x03cb9f67%2C0xdbbc%2C0x4cb8%2C%7B0xb9%2C0x66%2C0x32%2C0x99%2C0x51%2C0xe1%2C0x09%2C0x34%7D%7D%22%7D"
                ),
                r"^.*/waf\?json=%7B%20<redacted>%7D$",
            ),
        ]

    @missing_feature(
        context.library in ["golang", "nodejs", "ruby"],
        reason="tracer did not yet implemented the new version of query parameters obfuscation regex",
    )
    @irrelevant(context.library < "dotnet@2.41", reason="dotnet released the new version at 2.41.0")
    @irrelevant(context.library < "java@1.22.0", reason="java release the new version at 1.22.0")
    @irrelevant(context.library < "php@0.93.0", reason="php released the new version at 0.93.0")
    def test_url_with_sensitive_query_string(self):
        for r, tag in self.requests_sensitive_query_string:
            interfaces.library.add_span_tag_validation(
                request=r, tags={"http.url": tag}, value_as_regular_expression=True
            )

    def setup_multiple_matching_substring_legacy(self):
        self.request_multiple_matching_substring = weblog.get(
            "/waf?token=03cb9f67dbbc4cb8b9&key1=val1&key2=val2&pass=03cb9f67-dbbc-4cb8-b966-329951e10934&public_key=MDNjYjlmNjctZGJiYy00Y2I4LWI5NjYtMzI5OTUxZTEwOTM0&key3=val3&json=%7B%20%22sign%22%3A%20%22%7D%7D%22%7D"  # pylint: disable=line-too-long
        )

    # when tracer is updated, add (for example)
    @irrelevant(context.library >= "java@1.21.0", reason="java released the new version at 1.21.0")
    @irrelevant(context.library >= "python@1.18.0rc1", reason="python released the new version at 1.19.0")
    @irrelevant(context.library >= "dotnet@2.41", reason="dotnet released the new version at 2.41.0")
    @irrelevant(context.library >= "php@0.93.0", reason="php released the new version at 0.93.0")
    def test_multiple_matching_substring_legacy(self):
        tag = r"^.*/waf\?<redacted>&key1=val1&key2=val2&<redacted>&<redacted>&key3=val3&json=%7B%20%22<redacted>%7D$"  # pylint: disable=line-too-long
        interfaces.library.add_span_tag_validation(
            self.request_multiple_matching_substring, tags={"http.url": tag}, value_as_regular_expression=True
        )

    def setup_multiple_matching_substring(self):
        self.request_multiple_matching_substring = weblog.get(
            "/waf?token=03cb9f67dbbc4cb8b9&key1=val1&key2=val2&pass=03cb9f67-dbbc-4cb8-b966-329951e10934&public_key=MDNjYjlmNjctZGJiYy00Y2I4LWI5NjYtMzI5OTUxZTEwOTM0&key3=val3&application-key=dogkey&json=%7B%20%22sign%22%3A%20%22%7D%7D%22%7D&ecdsa-1-1%20aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaabbbbbaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa=%09test&json=%7B%20%22app-key%22%3A%20%22test%22%7D"  # pylint: disable=line-too-long
        )

    @missing_feature(
        context.library in ["golang", "nodejs", "ruby"],
        reason="tracer did not yet implemented the new version of query parameters obfuscation regex",
    )
    @irrelevant(context.library < "dotnet@2.41", reason="dotnet released the new version at 2.41.0")
    @irrelevant(context.library < "java@1.22.0", reason="java release the new version at 1.22.0")
    @irrelevant(context.library < "php@0.93.0", reason="php released the new version at 0.93.0")
    def test_multiple_matching_substring(self):
        tag = r"^.*/waf\?<redacted>&key1=val1&key2=val2&<redacted>&<redacted>&key3=val3&<redacted>&json=%7B%20<redacted>%7D&<redacted>&json=%7B%20<redacted>%7D$"  # pylint: disable=line-too-long
        interfaces.library.add_span_tag_validation(
            self.request_multiple_matching_substring, tags={"http.url": tag}, value_as_regular_expression=True
        )


@features.envoy_external_processing
@features.haproxy_stream_processing_offload
@features.security_events_metadata
@scenarios.external_processing
@scenarios.stream_processing_offload
@scenarios.default
class Test_StandardTagsUserAgent:
    """Tests to verify that libraries annotate spans with correct http.useragent tags"""

    def setup_useragent(self):
        self.r = weblog.get("/waf", headers={"user-agent": "Mistake Not ..."})

    def test_useragent(self):
        # system tests uses user-agent to ad a request id => allow anything at the end
        tags = {"http.useragent": r"Mistake Not \.\.\. .*"}
        interfaces.library.add_span_tag_validation(self.r, tags=tags, value_as_regular_expression=True)


@features.security_events_metadata
class Test_StandardTagsStatusCode:
    """Tests to verify that libraries annotate spans with correct http.status_code tags"""

    def setup_status_code(self):
        codes = ["200", "403", "404", "500"]
        self.requests = {code: weblog.get(f"/status?code={code}") for code in codes}

    def test_status_code(self):
        for code, r in self.requests.items():
            interfaces.library.add_span_tag_validation(request=r, tags={"http.status_code": code})


@features.security_events_metadata
class Test_StandardTagsRoute:
    """Tests to verify that libraries annotate spans with correct http.route tags"""

    def setup_route(self):
        self.r = weblog.get("/sample_rate_route/1")

    def test_route(self):
        assert self.r.status_code == 200

        tags = {"http.route": "/sample_rate_route/{i}"}

        # specify the route syntax if needed
        if context.library == "nodejs":
            tags["http.route"] = "/sample_rate_route/:i"
        if context.library == "golang":
            if "net-http" in context.weblog_variant:
                # net/http doesn't support parametrized routes but a path catches anything down the tree.
                tags["http.route"] = "/sample_rate_route/"
            if context.weblog_variant in ("gin", "echo", "uds-echo"):
                tags["http.route"] = "/sample_rate_route/:i"
        if context.library == "dotnet":
            tags["http.route"] = "/sample_rate_route/{i:int}"
        if context.library == "python":
            if context.weblog_variant in ("flask-poc", "uwsgi-poc", "uds-flask"):
                tags["http.route"] = "/sample_rate_route/<i>"
            elif context.weblog_variant in ("django-poc", "python3.12", "django-py3.13"):
                tags["http.route"] = "sample_rate_route/<int:i>"
        if context.library == "java":
            if context.weblog_variant in ("ratpack", "vertx3", "vertx4"):
                tags["http.route"] = "/sample_rate_route/:i"

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2118779066/Client+IP+addresses+resolution")
@features.envoy_external_processing
@features.haproxy_stream_processing_offload
@features.security_events_metadata
@scenarios.external_processing
@scenarios.stream_processing_offload
@scenarios.default
class Test_StandardTagsClientIp:
    """Tests to verify that libraries annotate spans with correct http.client_ip tags"""

    PUBLIC_IP = "43.43.43.43"
    PUBLIC_IPV6 = "2001:4860:4860:0:0:0:0:8888"
    # Some libraries might compress IPv6 addresses, so we need to accept both forms.
    VALID_PUBLIC_IPS = {PUBLIC_IP, PUBLIC_IPV6, "2001:4860:4860::8888"}
    FORWARD_HEADERS = {
        "x-forwarded-for": PUBLIC_IP,
        "x-real-ip": PUBLIC_IP,
        "true-client-ip": PUBLIC_IP,
        "x-client-ip": PUBLIC_IP,
        "forwarded-for": PUBLIC_IP,
        "x-cluster-client-ip": f"10.42.42.42, {PUBLIC_IP}, fe80::1",
    }
    FORWARD_HEADERS_VENDOR = {
        "fastly-client-ip": PUBLIC_IP,
        "cf-connecting-ip": PUBLIC_IP,
        "cf-connecting-ipv6": PUBLIC_IPV6,
    }

    def _setup_with_attack(self):
        if hasattr(self, "_setup_with_attack_done"):
            return
        self._setup_with_attack_done = True

        attack_headers = {"User-Agent": "Arachni/v1"}
        self.request_with_attack = weblog.get(
            "/waf/", headers=self.FORWARD_HEADERS | self.FORWARD_HEADERS_VENDOR | attack_headers
        )

    def _setup_without_attack(self):
        if hasattr(self, "_setup_without_attack_done"):
            return
        self._setup_without_attack_done = True

        self.requests_without_attack = {}
        for header, value in (self.FORWARD_HEADERS | self.FORWARD_HEADERS_VENDOR).items():
            self.requests_without_attack[header] = weblog.get("/waf/", headers={header: value})

    def _test_client_ip(self, forward_headers: dict[str, str]):
        for header in forward_headers:
            request = self.requests_without_attack[header]
            meta = self._get_root_span_meta(request)
            assert "http.client_ip" in meta, f"Missing http.client_ip for {header}"
            assert meta["http.client_ip"] in self.VALID_PUBLIC_IPS, f"Unexpected http.client_ip for {header}"

    def setup_client_ip(self):
        self._setup_without_attack()
        self._setup_with_attack()

    @bug(
        context.library < "java@1.11.0", reason="APMRP-360"
    )  # X-Client-Ip not supported, see https://github.com/DataDog/dd-trace-java/pull/4878
    def test_client_ip(self):
        """Test http.client_ip is always reported in the default scenario which has ASM enabled"""
        meta = self._get_root_span_meta(self.request_with_attack)
        assert "http.client_ip" in meta
        assert meta["http.client_ip"] == self.PUBLIC_IP

        self._test_client_ip(self.FORWARD_HEADERS)

    def setup_client_ip_vendor(self):
        self._setup_without_attack()

    @bug(context.library < "golang@1.69.0", reason="APMRP-360")
    @bug(
        context.library < "java@1.11.0", reason="APMRP-360"
    )  # not supported, see https://github.com/DataDog/dd-trace-java/pull/4878
    def test_client_ip_vendor(self):
        """Test http.client_ip is always reported in the default scenario which has ASM enabled when using vendor headers"""
        self._test_client_ip(self.FORWARD_HEADERS_VENDOR)

    def setup_client_ip_with_appsec_event(self):
        self._setup_with_attack()

    def test_client_ip_with_appsec_event(self):
        """Test that meta tag are correctly filled when an appsec event is present and ASM is enabled"""
        meta = self._get_root_span_meta(self.request_with_attack)
        assert "appsec.event" in meta
        assert "network.client.ip" in meta
        for header, value in self.FORWARD_HEADERS.items():
            tag = f"http.request.headers.{header.lower()}"
            assert tag in meta
            assert meta[tag] == value

    def setup_client_ip_with_appsec_event_and_vendor_headers(self):
        self._setup_with_attack()

    @missing_feature(
        context.library < "java@1.19.0", reason="missing fastly-client-ip, cf-connecting-ip, cf-connecting-ipv6"
    )
    @missing_feature(
        context.library < "golang@1.69.0", reason="missing fastly-client-ip, cf-connecting-ip, cf-connecting-ipv6"
    )
    @missing_feature(
        context.library < "nodejs@4.19.0", reason="missing fastly-client-ip, cf-connecting-ip, cf-connecting-ipv6"
    )
    @missing_feature(library="ruby", reason="missing fastly-client-ip, cf-connecting-ip, cf-connecting-ipv6")
    def test_client_ip_with_appsec_event_and_vendor_headers(self):
        """Test that meta tag are correctly filled when an appsec event is present and ASM is enabled, with vendor headers"""
        meta = self._get_root_span_meta(self.request_with_attack)
        for header, value in self.FORWARD_HEADERS_VENDOR.items():
            tag = f"http.request.headers.{header.lower()}"
            assert tag in meta, f"missing {tag} tag"
            assert meta[tag] == value

    def _get_root_span_meta(self, request: HttpResponse):
        span = interfaces.library.get_root_span(request)
        return span.get("meta", {})


@features.referrer_hostname
@scenarios.default
class Test_StandardTagsReferrerHostname:
    """Tests to verify that libraries annotate spans with correct http.referrer_hostname tags"""

    def setup_referrer_hostname(self):
        self.test_cases = [
            # (request, expected_hostname)
            (
                weblog.get("/status?code=200", headers={"referer": "https://app.datadoghq.com/path"}),
                "app.datadoghq.com",
            ),
            (
                weblog.get(
                    "/status?code=200",
                    headers={"referer": "https://user:pass@example.com:8080/path?query=123#fragment"},
                ),
                "example.com",
            ),
            (
                weblog.get("/status?code=200"),  # No referer header
                None,
            ),
            (
                weblog.get("/status?code=200", headers={"referer": ""}),  # Empty referer
                None,
            ),
            (
                weblog.get("/status?code=200", headers={"referer": "invalid-referer"}),  # Invalid referer
                None,
            ),
            (
                weblog.get("/status?code=200", headers={"referer": "file:///path/to/file"}),  # File scheme
                None,
            ),
            (
                weblog.get(
                    "/status?code=200", headers={"referer": "https://192.0.2.1:8080/path?query=123#fragment"}
                ),  # IP address
                "192.0.2.1",
            ),
        ]

    def test_referrer_hostname(self):
        """Test http.referrer_hostname is correctly extracted from the referer header"""
        for i, (request, expected_hostname) in enumerate(self.test_cases, 1):
            meta = self._get_root_span_meta(request)
            if expected_hostname is None:
                assert "http.referrer_hostname" not in meta, (
                    f'Test case #{i}: Expected no referrer hostname, but got "{meta.get("http.referrer_hostname")}"'
                )
            else:
                assert "http.referrer_hostname" in meta, (
                    f'Test case #{i}: Missing referrer hostname, but expected "{expected_hostname}"'
                )
                assert meta["http.referrer_hostname"] == expected_hostname, (
                    f"Test case #{i}: Expected hostname {expected_hostname}, got {meta.get('http.referrer_hostname')}"
                )

    def _get_root_span_meta(self, request: HttpResponse):
        span = interfaces.library.get_root_span(request)
        return span.get("meta", {})
