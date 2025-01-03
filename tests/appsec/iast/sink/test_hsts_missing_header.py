# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features, rfc, weblog
from ..utils import BaseSinkTest, validate_stack_traces


@features.iast_sink_hsts_missing_header
class Test_HstsMissingHeader(BaseSinkTest):
    """Test HSTS missing header detection."""

    vulnerability_type = "HSTS_HEADER_MISSING"
    http_method = "GET"
    insecure_endpoint = "/iast/hstsmissing/test_insecure"
    secure_endpoint = "/iast/hstsmissing/test_secure"
    data = {}
    headers = {"X-Forwarded-Proto": "https"}

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
class Test_HstsMissingHeader_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.get("/iast/hstsmissing/test_insecure", headers={"X-Forwarded-Proto": "https"})

    def test_stack_trace(self):
        validate_stack_traces(self.r)
