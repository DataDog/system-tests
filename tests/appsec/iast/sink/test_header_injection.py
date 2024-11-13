# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, features, missing_feature, weblog
from ..utils import BaseSinkTest, assert_iast_vulnerability


class _BaseTestHeaderInjectionReflectedExclusion:
    origin_header: None
    reflected_header: None
    headers: None

    exclusion_request: None
    no_exclusion_request: None

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
            request=self.no_exclusion_request, vulnerability_count=1, vulnerability_type="HEADER_INJECTION",
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
    location_map = {"nodejs": {"express4": "iast/index.js", "express4-typescript": "iast.ts"}}

    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()


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
