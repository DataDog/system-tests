# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import context, BaseTestCase, interfaces, irrelevant, released


class Test_StandardTags(BaseTestCase):
    """Tests to verify that libraries annotate spans with correct tags and metrics"""

    @released(dotnet="2.0.0", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
    def test_method(self):

        verbs = ["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "TRACE",  "PATCH"]

        for verb in verbs:
            data = None
            if verb == "POST" or verb == "PUT":
                data = "notmuchofabody"

            r = self._weblog_request(verb, "/waf", data=data)

            tags = {
                "http.method": verb,
            }
            interfaces.library.add_span_tag_validation(request=r, tags=tags)

    @released(dotnet="2.0.0", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
    def test_url_basic(self):
        r = self.weblog_get(f"/waf")

        tags = {
            "http.url": "http://weblog:7777/waf",
        }
        interfaces.library.add_span_tag_validation(request=r, tags=tags)

    @released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
    def test_url_with_query_string(self):
        r = self.weblog_get(f"/waf?key1=val1&key2=val2&key3=val3")

        tags = {
            "http.url": "http://weblog:7777/waf?key1=val1&key2=val2&key3=val3",
        }
        interfaces.library.add_span_tag_validation(request=r, tags=tags)

    @released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
    def test_useragent(self):
        r = self.weblog_get(f"/waf", headers={"user-agent": "Mistake Not ..."})

        tags = {
            "http.useragent": "Mistake Not ...",
        }
        interfaces.library.add_span_tag_validation(request=r, tags=tags)

    @released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
    def test_headers_headers(self):
        r = self.weblog_get(f"/waf")

        tags = {
            "http.request.headers.*": "",
        }
        interfaces.library.add_span_tag_validation(request=r, tags=tags)

    @released(dotnet="2.0.0", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
    def test_status_code(self):
        codes = ["200", "403", "404", "500"]
        for code in codes:
            r = self.weblog_get(f"/status?code=" + code)

            tags = {
                "http.status_code": code,
            }
            interfaces.library.add_span_tag_validation(request=r, tags=tags)

    @released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
    def test_route(self):
        r = self.weblog_get(f"/sample_rate_route/1")

        tags = {
            "http.route": "/sample_rate_route/{i}",
        }
        interfaces.library.add_span_tag_validation(request=r, tags=tags)

    @released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
    def test_client_ip(self):
        headers = {"X-Cluster-Client-IP": "10.42.42.42, 43.43.43.43, fe80::1"}
        r = self.weblog_get("/waf/", headers=headers)

        tags = {
            "http.client_ip": "43.43.43.43",
        }
        interfaces.library.add_span_tag_validation(request=r, tags=tags)

