# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import missing_feature, features, rfc, weblog
from tests.appsec.iast.utils import BaseSinkTest, validate_extended_location_data, validate_stack_traces


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


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestReflectionInjection_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.post("/iast/reflection_injection/test_insecure", data={"param": "ReflectionInjection"})

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class TestReflectionInjection_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "REFLECTION_INJECTION"

    def setup_extended_location_data(self):
        self.r = weblog.post("/iast/reflection_injection/test_insecure", data={"param": "ReflectionInjection"})

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type)
