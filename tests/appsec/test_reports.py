# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import socket


from utils import weblog, context, coverage, interfaces, bug, missing_feature, rfc


@bug(context.library == "python@1.1.0", reason="a PR was not included in the release")
@coverage.basic
class Test_StatusCode:
    """Appsec reports good status code"""

    def setup_basic(self):
        self.r = weblog.get("/path_that_doesn't_exists/", headers={"User-Agent": "Arachni/v1"})

    @bug(
        library="java",
        weblog_variant="spring-boot-openliberty",
        reason="https://datadoghq.atlassian.net/browse/APPSEC-6583",
    )
    def test_basic(self):
        assert self.r.status_code == 404
        interfaces.library.assert_waf_attack(self.r)

        def check_http_code_legacy(event):
            status_code = event["context"]["http"]["response"]["status"]
            assert status_code == 404, f"404 should have been reported, not {status_code}"

            return True

        def check_http_code(span, appsec_data):
            status_code = span["meta"]["http.status_code"]
            assert status_code == "404", f"404 should have been reported, not {status_code}"

            return True

        interfaces.library.validate_appsec(self.r, validator=check_http_code, legacy_validator=check_http_code_legacy)


@coverage.good
@missing_feature(
    True, reason="Bug on system test: with the runner on the host, we do not have the real IP from weblog POV"
)
class Test_HttpClientIP:
    """AppSec reports good http client IP"""

    def setup_http_remote_ip(self):
        headers = {"User-Agent": "Arachni/v1"}
        self.r = weblog.get("/waf/", headers=headers, stream=True)
        try:
            s = socket.fromfd(self.r.raw.fileno(), socket.AF_INET, socket.SOCK_STREAM)
            self.actual_remote_ip = s.getsockname()[0]
            self.r.close()
        except:
            self.actual_remote_ip = None

    def test_http_remote_ip(self):
        """AppSec reports the HTTP request peer IP."""

        def legacy_validator(event):
            remote_ip = event["context"]["http"]["request"]["remote_ip"]
            assert remote_ip == self.actual_remote_ip, f"request remote ip should be {self.actual_remote_ip}"

            return True

        def validator(span, appsec_data):
            ip = span["meta"]["network.client.ip"]
            assert ip == self.actual_remote_ip, f"network.client.ip should be {self.actual_remote_ip}"

            return True

        interfaces.library.validate_appsec(self.r, validator=validator, legacy_validator=legacy_validator)


@bug(context.library == "python@1.1.0", reason="a PR was not included in the release")
@coverage.good
class Test_Info:
    """Environment (production, staging) from DD_ENV variable"""

    def setup_service(self):
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_service(self):
        """Appsec reports the service information"""

        def _check_service_legacy(event):
            name = event["context"]["service"]["name"]
            environment = event["context"]["service"]["environment"]
            assert name == "weblog", f"weblog should have been reported, not {name}"
            assert environment == "system-tests", f"system-tests should have been reported, not {environment}"

            return True

        def _check_service(span, appsec_data):
            name = span.get("service")
            environment = span.get("meta", {}).get("env")
            assert name == "weblog", f"weblog should have been reported, not {name}"
            assert environment == "system-tests", f"system-tests should have been reported, not {environment}"

            return True

        interfaces.library.validate_appsec(self.r, legacy_validator=_check_service_legacy, validator=_check_service)


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2186870984/HTTP+header+collection")
@missing_feature(context.library == "ruby" and context.libddwaf_version is None)
@bug(context.library == "python@1.1.0", reason="a PR was not included in the release")
@coverage.good
class Test_RequestHeaders:
    """Request Headers for IP resolution"""

    def setup_http_request_headers(self):
        self.r = weblog.get(
            "/waf/",
            headers={
                "X-Forwarded-For": "42.42.42.42, 43.43.43.43",
                "X-Client-IP": "42.42.42.42, 43.43.43.43",
                "X-Real-IP": "42.42.42.42, 43.43.43.43",
                "X-Forwarded": "42.42.42.42, 43.43.43.43",
                "X-Cluster-Client-IP": "42.42.42.42, 43.43.43.43",
                "Forwarded-For": "42.42.42.42, 43.43.43.43",
                "Forwarded": "42.42.42.42, 43.43.43.43",
                "Via": "42.42.42.42, 43.43.43.43",
                "True-Client-IP": "42.42.42.42, 43.43.43.43",
                "User-Agent": "Arachni/v1",
            },
        )

    @bug(context.library < "dotnet@2.1.0")
    def test_http_request_headers(self):
        """AppSec reports the HTTP headers used for actor IP detection."""

        interfaces.library.add_appsec_reported_header(self.r, "x-forwarded-for")
        interfaces.library.add_appsec_reported_header(self.r, "x-client-ip")
        interfaces.library.add_appsec_reported_header(self.r, "x-real-ip")
        interfaces.library.add_appsec_reported_header(self.r, "x-forwarded")
        interfaces.library.add_appsec_reported_header(self.r, "x-cluster-client-ip")
        interfaces.library.add_appsec_reported_header(self.r, "forwarded-for")
        interfaces.library.add_appsec_reported_header(self.r, "forwarded")
        interfaces.library.add_appsec_reported_header(self.r, "via")
        interfaces.library.add_appsec_reported_header(self.r, "true-client-ip")


@coverage.basic
class Test_TagsFromRule:
    """Tags (Category & event type) from the rule"""

    def setup_basic(self):
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    @missing_feature(weblog_variant="spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_basic(self):
        """attack timestamp is given by start property of span"""

        for _, _, _, appsec_data in interfaces.library.get_appsec_events(request=self.r):
            for trigger in appsec_data["triggers"]:
                assert "rule" in trigger
                assert "tags" in trigger["rule"]
                assert "type" in trigger["rule"]["tags"]
                assert "category" in trigger["rule"]["tags"]


@coverage.basic
class Test_ExtraTagsFromRule:
    """Extra tags may be added to the rule match since libddwaf 1.10.0"""

    def setup_basic(self):
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_basic(self):
        for _, _, _, appsec_data in interfaces.library.get_appsec_events(request=self.r):
            for trigger in appsec_data["triggers"]:
                assert "rule" in trigger
                assert "tags" in trigger["rule"]
                assert "tool_name" in trigger["rule"]["tags"]


@coverage.basic
class Test_AttackTimestamp:
    """Attack timestamp"""

    def setup_basic(self):
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    @missing_feature(weblog_variant="spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_basic(self):
        """attack timestamp is given by start property of span"""

        for _, _, span, _ in interfaces.library.get_appsec_events(request=self.r):
            assert "start" in span, "span should contain start property"
            assert isinstance(span["start"], int), f"start property should an int, not {repr(span['start'])}"
