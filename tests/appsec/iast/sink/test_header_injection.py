# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, features, missing_feature
from ..utils import BaseSinkTest, BaseTestHeaderInjectionReflectedExclusion


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
class TestHeaderInjectionExclusionPragma(BaseTestHeaderInjectionReflectedExclusion):
    """Verify Header injection Pragma reflexion exclusion"""

    origin_header = "cache-control"
    reflected_header = "pragma"
    headers = {"cache-control": "cacheControlValue"}


@features.iast_sink_header_injection
class TestHeaderInjectionExclusionTransferEncoding(BaseTestHeaderInjectionReflectedExclusion):
    """Verify Header injection Transfer-Encoding reflexion exclusion"""

    origin_header = "accept-encoding"
    reflected_header = "transfer-encoding"
    headers = {"accept-encoding": "foo, bar"}


@features.iast_sink_header_injection
class TestHeaderInjectionExclusionContentEncoding(BaseTestHeaderInjectionReflectedExclusion):
    """Verify Header injection Content-Encoding reflexion exclusion"""

    origin_header = "accept-encoding"
    reflected_header = "content-encoding"
    headers = {"accept-encoding": "foo, bar"}


@features.iast_sink_header_injection
class TestHeaderInjectionExclusionAccessControlAllow(BaseTestHeaderInjectionReflectedExclusion):
    """Verify Header injection Access-Control-Allow-* reflexion exclusion"""

    origin_header = "x-custom-header"
    reflected_header = "access-control-allow-origin"
    headers = {"x-custom-header": "allowed-origin"}
