# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import bug, context, coverage, interfaces, irrelevant, missing_feature, released, rfc, weblog


@released(java="0.102.0")
@coverage.good
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
    @bug(weblog_variant="spring-boot-payara", reason="This weblog variant is currently not accepting TRACE")
    def test_method_trace(self):
        interfaces.library.add_span_tag_validation(request=self.trace_request, tags={"http.method": "TRACE"})


@released(java="0.107.1")
@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2490990623/QueryString+-+Sensitive+Data+Obfuscation")
@coverage.basic
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
            (
                weblog.get(
                    "/waf?json=%7B%20%22sign%22%3A%20%22%7B0x03cb9f67%2C0xdbbc%2C0x4cb8%2C%7B0xb9%2C0x66%2C0x32%2C0x99%2C0x51%2C0xe1%2C0x09%2C0x34%7D%7D%22%7D"
                ),
                r"^.*/waf\?json=%7B%20<redacted>%7D$",
            ),
        ]

    @missing_feature(
        context.library in ["dotnet", "golang", "nodejs", "php", "ruby"],
        reason="tracer did not yet implemented the new version of query parameters obfuscation regex",
    )
    @missing_feature(context.library < "java@1.21.0", reason="previous obfuscation regex")
    @irrelevant(context.library < "python@1.19", reason="python released the new version at 1.19.0")
    def test_url_with_sensitive_query_string(self):
        for r, tag in self.requests_sensitive_query_string:
            interfaces.library.add_span_tag_validation(
                request=r, tags={"http.url": tag}, value_as_regular_expression=True
            )

    def setup_multiple_matching_substring_legacy(self):
        self.request_multiple_matching_substring = weblog.get(
            "/waf?token=03cb9f67dbbc4cb8b9&key1=val1&key2=val2&pass=03cb9f67-dbbc-4cb8-b966-329951e10934&public_key=MDNjYjlmNjctZGJiYy00Y2I4LWI5NjYtMzI5OTUxZTEwOTM0&key3=val3&json=%7B%20%22sign%22%3A%20%22%7D%7D%22%7D"  # pylint: disable=line-too-long
        )

    # when tracer is updated, add (for exemple)
    @irrelevant(context.library >= "java@1.21.0", reason="java released the new version at 1.21.0")
    @irrelevant(context.library >= "python@1.18.0rc1", reason="python released the new version at 1.19.0")
    def test_multiple_matching_substring_legacy(self):
        tag = r"^.*/waf\?<redacted>&key1=val1&key2=val2&<redacted>&<redacted>&key3=val3&json=%7B%20%22<redacted>%7D$"  # pylint: disable=line-too-long
        interfaces.library.add_span_tag_validation(
            self.request_multiple_matching_substring, tags={"http.url": tag}, value_as_regular_expression=True
        )

    def setup_multiple_matching_substring(self):
        self.request_multiple_matching_substring = weblog.get(
            "/waf?token=03cb9f67dbbc4cb8b9&key1=val1&key2=val2&pass=03cb9f67-dbbc-4cb8-b966-329951e10934&public_key=MDNjYjlmNjctZGJiYy00Y2I4LWI5NjYtMzI5OTUxZTEwOTM0&key3=val3&json=%7B%20%22sign%22%3A%20%22%7D%7D%22%7D"  # pylint: disable=line-too-long
        )

    @missing_feature(
        context.library in ["dotnet", "golang", "nodejs", "php", "ruby"],
        reason="tracer did not yet implemented the new version of query parameters obfuscation regex",
    )
    @missing_feature(context.library < "java@1.21.0", reason="previous obfuscation regex")
    @irrelevant(context.library < "python@1.19", reason="python released the new version at 1.19.0")
    def test_multiple_matching_substring(self):
        tag = r"^.*/waf\?<redacted>&key1=val1&key2=val2&<redacted>&<redacted>&key3=val3&json=%7B%20<redacted>%7D$"  # pylint: disable=line-too-long
        interfaces.library.add_span_tag_validation(
            self.request_multiple_matching_substring, tags={"http.url": tag}, value_as_regular_expression=True
        )


@released(java="0.107.1")
@coverage.basic
class Test_StandardTagsUserAgent:
    """Tests to verify that libraries annotate spans with correct http.useragent tags"""

    def setup_useragent(self):
        self.r = weblog.get("/waf", headers={"user-agent": "Mistake Not ..."})

    def test_useragent(self):
        # system tests uses user-agent to ad a request id => allow anything at the end
        tags = {"http.useragent": r"Mistake Not \.\.\. .*"}
        interfaces.library.add_span_tag_validation(self.r, tags=tags, value_as_regular_expression=True)


@released(java="0.102.0")
@coverage.good
class Test_StandardTagsStatusCode:
    """Tests to verify that libraries annotate spans with correct http.status_code tags"""

    def setup_status_code(self):
        codes = ["200", "403", "404", "500"]
        self.requests = {code: weblog.get(f"/status?code={code}") for code in codes}

    def test_status_code(self):
        for code, r in self.requests.items():
            interfaces.library.add_span_tag_validation(request=r, tags={"http.status_code": code})


@released(java={"spring-boot": "0.102.0", "spring-boot-jetty": "0.102.0", "*": "?"})
@irrelevant(library="ruby", weblog_variant="rack", reason="rack can not access route pattern")
@missing_feature(
    context.library == "ruby" and context.weblog_variant in ("rails", "sinatra14", "sinatra20", "sinatra21")
)
@coverage.basic
class Test_StandardTagsRoute:
    """Tests to verify that libraries annotate spans with correct http.route tags"""

    def setup_route(self):
        self.r = weblog.get("/sample_rate_route/1")

    def test_route(self):
        tags = {"http.route": "/sample_rate_route/{i}"}

        # specify the route syntax if needed
        if context.library == "nodejs":
            tags["http.route"] = "/sample_rate_route/:i"
        if context.library == "golang":
            if context.weblog_variant == "net-http":
                # net/http doesn't support parametrized routes but a path catches anything down the tree.
                tags["http.route"] = "/sample_rate_route/"
            if context.weblog_variant in ("gin", "echo", "uds-echo"):
                tags["http.route"] = "/sample_rate_route/:i"
        if context.library == "dotnet":
            tags["http.route"] = "/sample_rate_route/{i:int}"
        if context.library == "python":
            if context.weblog_variant in ("flask-poc", "uwsgi-poc", "uds-flask"):
                tags["http.route"] = "/sample_rate_route/<i>"
            elif context.weblog_variant == "django-poc":
                tags["http.route"] = "sample_rate_route/<int:i>"

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2118779066/Client+IP+addresses+resolution")
@released(java="0.114.0")
@missing_feature(weblog_variant="akka-http", reason="No AppSec support")
@missing_feature(weblog_variant="spring-boot-payara", reason="No AppSec support")
@missing_feature(weblog_variant="spring-boot-3-native", reason="GraalVM. Tracing support only")
@coverage.basic
class Test_StandardTagsClientIp:
    """Tests to verify that libraries annotate spans with correct http.client_ip tags"""

    def setup(self):
        """Send two_request, on with an attack, another one without attack"""

        if hasattr(self, "setup_done"):
            return

        self.setup_done = True

        headers = {"X-Cluster-Client-IP": "10.42.42.42, 43.43.43.43, fe80::1"}
        attack_headers = {"User-Agent": "Arachni/v1"}

        self.request_with_attack = weblog.get("/waf/", headers=headers | attack_headers)
        self.request_without_attack = weblog.get("/waf/", headers=headers)

    def setup_client_ip(self):
        self.setup()

    def test_client_ip(self):
        """Test http.client_ip is always reported in the default scenario which has ASM enabled"""

        def validator(span):
            meta = span.get("meta", {})
            assert "http.client_ip" in meta, "missing http.client_ip tag"

            got = meta["http.client_ip"]
            expected = "43.43.43.43"
            assert got == expected, f"unexpected http.client_ip value {got} instead of {expected}"

            return True

        interfaces.library.validate_spans(request=self.request_with_attack, validator=validator)
        interfaces.library.validate_spans(request=self.request_without_attack, validator=validator)

    def setup_client_ip_with_appsec_event(self):
        self.setup()

    def test_client_ip_with_appsec_event(self):
        """Test that meta tag are correctly filled when an appsec event is present and ASM is enabled"""

        def validator(span):
            meta = span.get("meta", {})

            # ASM should report extra IP-related span tags.
            assert "appsec.event" in meta, "missing appsec.event tag"
            assert "network.client.ip" in meta, "missing network.client.ip tag"
            assert (
                "http.request.headers.x-cluster-client-ip" in meta
            ), "missing http.request.headers.x-cluster-client-ip tag"

            return True

        interfaces.library.validate_spans(request=self.request_with_attack, validator=validator)
