# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features, rfc, weblog
from ..utils import BaseSinkTest, validate_stack_traces


@features.iast_sink_code_injection
class TestCodeInjection(BaseSinkTest):
    """Test command injection detection."""

    vulnerability_type = "CODE_INJECTION"
    http_method = "POST"
    insecure_endpoint = "/iast/code_injection/test_insecure"
    secure_endpoint = "/iast/code_injection/test_secure"
    data = {"code": "1+2"}
    location_map = {
        "nodejs": {"express4": "iast/index.js", "express4-typescript": "iast.ts", "express5": "iast/index.js"},
    }

    @missing_feature(library="nodejs", reason="Instrumented metric not implemented")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestCodeInjection_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.post("/iast/code_injection/test_insecure", data={"code": "1+2"})

    def test_stack_trace(self):
        validate_stack_traces(self.r)
