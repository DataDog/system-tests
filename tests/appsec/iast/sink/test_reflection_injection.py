# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import missing_feature, features
from .._test_iast_fixtures import BaseSinkTest


@features.iast_sink_reflection_injection
class TestReflectionInjection(BaseSinkTest):
    """Test Reflection Injection detection."""

    vulnerability_type = "REFLECTION_INJECTION"
    http_method = "POST"
    insecure_endpoint = "/iast/reflection_injection/test_insecure"
    secure_endpoint = "/iast/reflection_injection/test_secure"
    data = {"param": "ReflectionInjection"}
    location_map = {"java": "com.datadoghq.system_tests.iast.utils.ReflectionExamples"}

    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()

    def test_secure(self):
        super().test_secure()
