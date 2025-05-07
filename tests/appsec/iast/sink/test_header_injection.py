# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, features, missing_feature, rfc, weblog, HttpResponse, bug
from tests.appsec.iast.utils import (
    BaseSinkTest,
    validate_extended_location_data,
    validate_stack_traces,
    assert_iast_vulnerability,
)


class _BaseTestHeaderInjectionReflectedExclusion:
    origin_header: str
    reflected_header: str
    headers: dict

    exclusion_request: HttpResponse
    no_exclusion_request: HttpResponse

    def setup_no_exclusion(self):
        assert self.origin_header is not None, f"Please set {self}.origin_header"
        assert isinstance(self.origin_header, str), f"Please set {self}.origin_header"
        assert self.reflected_header is not None, f"Please set {self}.reflected_header"
        assert isinstance(self.reflected_header, str), f"Please set {self}.reflected_header"

        self.no_exclusion_request = weblog.get(
            path="/iast/header_injection/reflected/no-exclusion",
            params={"origin": self.origin_header, "reflected": self.reflected_header},
        )

    def test_no_exclusion(self):
        assert_iast_vulnerability(
            request=self.no_exclusion_request, vulnerability_count=1, vulnerability_type="HEADER_INJECTION"
        )

    def setup_exclusion(self):
        assert self.origin_header is not None, f"Please set {self}.origin_header"
        assert isinstance(self.origin_header, str), f"Please set {self}.origin_header"
        assert self.reflected_header is not None, f"Please set {self}.reflected_header"
        assert isinstance(self.reflected_header, str), f"Please set {self}.reflected_header"

        self.exclusion_request = weblog.get(
            path="/iast/header_injection/reflected/exclusion",
            params={"origin": self.origin_header, "reflected": self.reflected_header},
            headers=self.headers,
        )

    def test_exclusion(self):
        BaseSinkTest.assert_no_iast_event(self.exclusion_request)


@features.iast_sink_header_injection
class TestHeaderInjection(BaseSinkTest):
    """Verify Header injection detection"""

    vulnerability_type = "HEADER_INJECTION"
    http_method = "POST"
    insecure_endpoint = "/iast/header_injection/test_insecure"
    secure_endpoint = "/iast/header_injection/test_secure"
    data = {"test": "dummyvalue"}
    location_map = {
        "nodejs": {"express4": "iast/index.js", "express4-typescript": "iast.ts", "express5": "iast/index.js"}
    }

    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestHeaderInjection_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.post("/iast/header_injection/test_insecure", data={"test": "dummyvalue"})

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@features.iast_sink_header_injection
class TestHeaderInjectionExclusionAccessControlAllow(_BaseTestHeaderInjectionReflectedExclusion):
    """Verify Header injection Access-Control-Allow-* reflexion exclusion"""

    origin_header = "x-custom-header"
    reflected_header = "access-control-allow-origin"
    headers = {"x-custom-header": "allowed-origin"}


@features.iast_sink_header_injection
class TestHeaderInjectionExclusionContentEncoding(_BaseTestHeaderInjectionReflectedExclusion):
    """Verify Header injection Content-Encoding reflexion exclusion"""

    origin_header = "accept-encoding"
    reflected_header = "content-encoding"
    headers = {"accept-encoding": "foo, bar"}


@features.iast_sink_header_injection
class TestHeaderInjectionExclusionPragma(_BaseTestHeaderInjectionReflectedExclusion):
    """Verify Header injection Pragma reflexion exclusion"""

    origin_header = "cache-control"
    reflected_header = "pragma"
    headers = {"cache-control": "cacheControlValue"}


@features.iast_sink_header_injection
class TestHeaderInjectionExclusionTransferEncoding(_BaseTestHeaderInjectionReflectedExclusion):
    """Verify Header injection Transfer-Encoding reflexion exclusion"""

    origin_header = "accept-encoding"
    reflected_header = "transfer-encoding"
    headers = {"accept-encoding": "foo, bar"}


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class TestHeaderInjection_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "HEADER_INJECTION"

    def setup_extended_location_data(self):
        self.r = weblog.post("/iast/header_injection/test_insecure", data={"test": "dummyvalue"})

    @bug(context.library > "python@3.7.0", reason="APPSEC-57552")
    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type)
