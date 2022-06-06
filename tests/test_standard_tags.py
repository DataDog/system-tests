# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

import pytest

from utils import context, coverage, BaseTestCase, interfaces, irrelevant, released

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(dotnet="2.0.0", golang="?", java="?", nodejs="?", php="0.74.0", python="?", ruby="?")
@coverage.good
class Test_StandardTagsMethod(BaseTestCase):
    """Tests to verify that libraries annotate spans with correct http.method tags"""

    def test_method(self):

        verbs = ["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "TRACE", "PATCH"]

        for verb in verbs:
            data = None
            if verb == "POST" or verb == "PUT":
                data = "notmuchofabody"

            r = self._weblog_request(verb, "/waf", data=data)

            tags = {
                "http.method": verb,
            }
            interfaces.library.add_span_tag_validation(request=r, tags=tags)


@released(dotnet="?", golang="?", java="?", nodejs="?", php="0.74.0", python="?", ruby="?")
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


@released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
@coverage.basic
class Test_StandardTagsUserAgent(BaseTestCase):
    """Tests to verify that libraries annotate spans with correct http.useragent tags"""

    def test_useragent(self):
        r = self.weblog_get(f"/waf", headers={"user-agent": "Mistake Not ..."})

        tags = {
            "http.useragent": "Mistake Not ...",
        }
        interfaces.library.add_span_tag_validation(request=r, tags=tags)


@released(dotnet="2.0.0", golang="?", java="?", nodejs="?", php="0.74.0", python="?", ruby="?")
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


@released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
@coverage.basic
class Test_StandardTagsRoute(BaseTestCase):
    """Tests to verify that libraries annotate spans with correct http.route tags"""

    def test_route(self):
        r = self.weblog_get(f"/sample_rate_route/1")

        tags = {
            "http.route": "/sample_rate_route/{i}",
        }
        interfaces.library.add_span_tag_validation(request=r, tags=tags)


@released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
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
