# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import bug, context, missing_feature, features, rfc, weblog
from ..utils import BaseSinkTest, validate_extended_location_data, validate_stack_traces


@features.iast_sink_ssrf
class TestSSRF(BaseSinkTest):
    """Test ssrf detection."""

    vulnerability_type = "SSRF"
    http_method = "POST"
    insecure_endpoint = "/iast/ssrf/test_insecure"
    secure_endpoint = "/iast/ssrf/test_secure"
    data = {"url": "https://www.datadoghq.com"}
    location_map = {
        "java": "com.datadoghq.system_tests.iast.utils.SsrfExamples",
        "nodejs": {"express4": "iast/index.js", "express4-typescript": "iast.ts", "express5": "iast/index.js"},
        "python": {"flask-poc": "app.py", "django-poc": "app/urls.py", "fastapi": "main.py"},
    }

    @bug(context.library < "java@1.14.0", reason="APMRP-360")
    def test_insecure(self):
        super().test_insecure()

    @missing_feature(library="nodejs", reason="Endpoint not implemented")
    @missing_feature(library="java", reason="Endpoint not implemented")
    def test_secure(self):
        super().test_secure()

    @missing_feature(library="dotnet", reason="Not implemented yet")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestSSRF_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.post("/iast/ssrf/test_insecure", data={"url": "https://www.datadoghq.com"})

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class TestSSRF_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "SSRF"

    def setup_extended_location_data(self):
        self.r = weblog.post("/iast/ssrf/test_insecure", data={"url": "https://www.datadoghq.com"})

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type)
