# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import bug, context, coverage, missing_feature, features
from .._test_iast_fixtures import BaseSinkTest


@features.iast_sink_trustboundaryviolation
@bug(context.library < "java@1.22.0", reason="APPSEC-12201")
@coverage.basic
class Test_TrustBoundaryViolation(BaseSinkTest):
    """Test Trust Boundary Violation detection."""

    vulnerability_type = "TRUST_BOUNDARY_VIOLATION"
    http_method = "GET"
    insecure_endpoint = "/iast/trust-boundary-violation/test_insecure"
    secure_endpoint = "/iast/trust-boundary-violation/test_secure"
    params = {"username": "shaquille_oatmeal", "password": "123456"}

    @missing_feature(library="nodejs", reason="Metrics implemented")
    @missing_feature(library="dotnet", reason="Metrics implemented")
    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(library="nodejs", reason="Metrics implemented")
    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()
