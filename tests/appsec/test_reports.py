# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
from utils import weblog, context, interfaces, bug, scenarios, rfc, features


@bug(context.library == "python@1.1.0", reason="APMRP-360")
@features.security_events_metadata
class Test_StatusCode:
    """Appsec reports good status code"""

    def setup_basic(self):
        self.r = weblog.get("/path_that_doesn't_exists", headers={"User-Agent": "Arachni/v1"})

    @bug(library="java", weblog_variant="spring-boot-openliberty", reason="APPSEC-6583")
    def test_basic(self):
        assert self.r.status_code == 404
        interfaces.library.assert_waf_attack(self.r)

        def check_http_code_legacy(event):
            status_code = event["context"]["http"]["response"]["status"]
            assert status_code == 404, f"404 should have been reported, not {status_code}"

            return True

        def check_http_code(span, appsec_data):  # noqa: ARG001
            status_code = span["meta"]["http.status_code"]
            assert status_code == "404", f"404 should have been reported, not {status_code}"

            return True

        interfaces.library.validate_appsec(self.r, validator=check_http_code, legacy_validator=check_http_code_legacy)


@bug(context.library == "python@1.1.0", reason="APMRP-360")
@features.security_events_metadata
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

        def _check_service(span, appsec_data):  # noqa: ARG001
            name = span.get("service")
            environment = span.get("meta", {}).get("env")
            assert name == "weblog", f"weblog should have been reported, not {name}"
            assert environment == "system-tests", f"system-tests should have been reported, not {environment}"

            return True

        interfaces.library.validate_appsec(self.r, legacy_validator=_check_service_legacy, validator=_check_service)


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2186870984/HTTP+header+collection")
@bug(context.library == "python@1.1.0", reason="APMRP-360")
@features.envoy_external_processing
@features.haproxy_stream_processing_offload
@features.security_events_metadata
@scenarios.external_processing
@scenarios.stream_processing_offload
@scenarios.default
@scenarios.appsec_lambda_default
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

    @bug(context.library < "dotnet@2.1.0", reason="APMRP-360")
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


@features.envoy_external_processing
@features.haproxy_stream_processing_offload
@features.security_events_metadata
@scenarios.external_processing
@scenarios.stream_processing_offload
@scenarios.default
@scenarios.appsec_lambda_default
class Test_TagsFromRule:
    """Tags tags from the rule"""

    def _setup(self):
        if not hasattr(self, "r"):
            self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def setup_type(self):
        self._setup()

    def test_type(self):
        """Type tag is set"""
        for trigger in _get_appsec_triggers(self.r):
            assert "type" in trigger["rule"]["tags"]

    def setup_category(self):
        self._setup()

    def test_category(self):
        """Category tag is set"""
        for trigger in _get_appsec_triggers(self.r):
            assert "category" in trigger["rule"]["tags"]


@features.envoy_external_processing
@features.haproxy_stream_processing_offload
@features.security_events_metadata
@scenarios.external_processing
@scenarios.stream_processing_offload
@scenarios.default
@scenarios.appsec_lambda_default
class Test_ExtraTagsFromRule:
    """Extra tags may be added to the rule match since libddwaf 1.10.0"""

    def setup_tool_name(self):
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_tool_name(self):
        """Tool name tag is set"""
        for trigger in _get_appsec_triggers(self.r):
            assert "tool_name" in trigger["rule"]["tags"]


def _get_appsec_triggers(request):
    datas = [appsec_data for _, _, _, appsec_data in interfaces.library.get_appsec_events(request=request)]
    assert datas, "No AppSec events found"
    triggers = []
    for data in datas:
        triggers += data["triggers"]
    assert triggers, "No triggers found"
    for trigger in triggers:
        assert "rule" in trigger
        assert "tags" in trigger["rule"]
    return triggers


@features.envoy_external_processing
@features.haproxy_stream_processing_offload
@features.security_events_metadata
@scenarios.external_processing
@scenarios.stream_processing_offload
@scenarios.default
@scenarios.appsec_lambda_default
class Test_AttackTimestamp:
    """Attack timestamp"""

    def setup_basic(self):
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_basic(self):
        """Attack timestamp is given by start property of span"""
        spans = [span for _, _, span, _ in interfaces.library.get_appsec_events(request=self.r)]
        assert spans, "No AppSec events found"
        for span in spans:
            assert "start" in span, "span should contain start property"
            assert isinstance(span["start"], int), f"start property should an int, not {span['start']!r}"
