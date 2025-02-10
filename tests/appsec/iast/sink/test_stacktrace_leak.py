# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2025 Datadog, Inc.


from utils import features, rfc, weblog
from ..utils import BaseSinkTest, validate_stack_traces


@features.iast_stack_trace
class TestStackTraceLeak(BaseSinkTest):
    """Test stack trace leak detection."""

    vulnerability_type = "STACK_TRACE_LEAK"
    http_method = "GET"
    insecure_endpoint = "/iast/stack_trace_leak/test_insecure"
    secure_endpoint = "/iast/stack_trace_leak/test_secure"
    data = {}
    location_map = {}

    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestStackTraceLeak_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.get("/iast/stack_trace_leak/test_insecure")

    def test_stack_trace(self):
        validate_stack_traces(self.r)
