# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

import pytest

from utils import context, coverage, BaseTestCase, interfaces, irrelevant, released, rfc

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(dotnet="2.0.0", golang="1.39.0", java="0.102.0", nodejs="2.0.0", php="0.75.0", python="1.2.1", ruby="?")
@coverage.good
class Test_StandardTagsMethod(BaseTestCase):
    """Tests to verify that libraries annotate spans with correct http.method tags"""

    def test_method(self):

        verbs = ["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]

        for verb in verbs:
            data = None
            if verb == "POST" or verb == "PUT":
                data = "notmuchofabody"

            r = self._weblog_request(verb, "/waf", data=data)

            tags = {
                "http.method": verb,
            }
            interfaces.library.add_span_tag_validation(request=r, tags=tags)

    @irrelevant(library="php", reason="Trace method does not reach php-land")
    def test_method_trace(self):
        r = self._weblog_request("TRACE", "/waf", data=None)
        tags = {
            "http.method": "TRACE",
        }
        interfaces.library.add_span_tag_validation(request=r, tags=tags)


@released(dotnet="?", golang="1.40.0", java="?", nodejs="?", php="0.76.0", python="?", ruby="?")
@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2490990623/QueryString+-+Sensitive+Data+Obfuscation")
@coverage.basic
class Test_StandardTagsUrl(BaseTestCase):
    """Tests to verify that libraries annotate spans with correct http.url tags"""

    def test_url_basic(self):
        r = self.weblog_get(f"/waf")

        tags = {
            "http.url": "http://weblog:7777/waf",
        }
        interfaces.library.add_span_tag_validation(request=r, tags=tags)

    def test_url_with_query_string(self):
        r = self.weblog_get(f"/waf?key1=val1&key2=val2&key3=val3")

        tags = {
            "http.url": "http://weblog:7777/waf?key1=val1&key2=val2&key3=val3",
        }
        interfaces.library.add_span_tag_validation(request=r, tags=tags)

    def test_url_with_sensitive_query_string(self):
        tests = {
            "/waf?pass=03cb9f67-dbbc-4cb8-b966-329951e10934&key2=val2&key3=val3": "http://weblog:7777/waf?<redacted>&key2=val2&key3=val3",
            "/waf?key1=val1&public_key=MDNjYjlmNjctZGJiYy00Y2I4LWI5NjYtMzI5OTUxZTEwOTM0&key3=val3": "http://weblog:7777/waf?key1=val1&<redacted>&key3=val3",
            "/waf?key1=val1&key2=val2&token=03cb9f67dbbc4cb8b966329951e10934": "http://weblog:7777/waf?key1=val1&key2=val2&<redacted>",
            "/waf?json=%7B%20%22sign%22%3A%20%22%7B0x03cb9f67%2C0xdbbc%2C0x4cb8%2C%7B0xb9%2C0x66%2C0x32%2C0x99%2C0x51%2C0xe1%2C0x09%2C0x34%7D%7D%22%7D": "http://weblog:7777/waf?json=%7B%20%22<redacted>%7D",
        }

        for url in tests:
            r = self.weblog_get(url)

            tags = {
                "http.url": tests[url],
            }
            interfaces.library.add_span_tag_validation(request=r, tags=tags)


@released(dotnet="?", golang="1.39.0", java="?", nodejs="2.9.0", php="0.75.0", python="?", ruby="?")
@coverage.basic
class Test_StandardTagsUserAgent(BaseTestCase):
    """Tests to verify that libraries annotate spans with correct http.useragent tags"""

    def test_useragent(self):
        r = self.weblog_get(f"/waf", headers={"user-agent": "Mistake Not ..."})

        # system tests uses user-agent to ad a request id => allow anything at the end
        tags = {"http.useragent": r"Mistake Not \.\.\. .*"}
        interfaces.library.add_span_tag_validation(request=r, tags=tags, value_as_regular_expression=True)


@released(dotnet="2.0.0", golang="1.39.0", java="0.102.0", nodejs="2.0.0", php="0.75.0", python="?", ruby="?")
@coverage.good
class Test_StandardTagsStatusCode(BaseTestCase):
    """Tests to verify that libraries annotate spans with correct http.status_code tags"""

    def test_status_code(self):
        codes = ["200", "403", "404", "500"]
        for code in codes:
            r = self.weblog_get(f"/status?code=" + code)

            tags = {
                "http.status_code": code,
            }
            interfaces.library.add_span_tag_validation(request=r, tags=tags)


@released(dotnet="?", golang="1.39.0", nodejs="2.0.0", php="?", python="?", ruby="?")
@released(java={"spring-boot": "0.102.0", "spring-boot-jetty": "0.102.0", "*": "?"})
@coverage.basic
class Test_StandardTagsRoute(BaseTestCase):
    """Tests to verify that libraries annotate spans with correct http.route tags"""

    @irrelevant(
        context.library == "golang" and context.weblog_variant == "net-http",
        reason="net-http does not handle route parameters",
    )
    def test_route(self):
        r = self.weblog_get(f"/sample_rate_route/1")

        tags = {
            "http.route": "/sample_rate_route/{i}",
        }

        # specify the route syntax if needed
        if context.library == "nodejs":
            tags["http.route"] = "/sample_rate_route/:i"
        if context.library == "golang" and context.weblog_variant not in ["gorilla", "chi"]:
            tags["http.route"] = "/sample_rate_route/:i"

        interfaces.library.add_span_tag_validation(request=r, tags=tags)


@released(dotnet="?", golang="1.39.0", java="?", nodejs="?", php="0.76.0", python="?", ruby="?")
@coverage.basic
class Test_StandardTagsClientIp(BaseTestCase):
    """Tests to verify that libraries annotate spans with correct http.client_ip tags"""

    def test_client_ip(self):
        headers = {"X-Cluster-Client-IP": "10.42.42.42, 43.43.43.43, fe80::1"}
        r = self.weblog_get("/waf/", headers=headers)

        tags = {
            "http.client_ip": "43.43.43.43",
        }
        interfaces.library.add_span_tag_validation(request=r, tags=tags)
