# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features, rfc, weblog
from ..utils import BaseSinkTest, validate_stack_traces


@features.iast_sink_xcontentsniffing
class Test_XContentSniffing(BaseSinkTest):
    """Test missing X-Content-Options header detection."""

    vulnerability_type = "XCONTENTTYPE_HEADER_MISSING"
    http_method = "GET"
    insecure_endpoint = "/iast/xcontent-missing-header/test_insecure"
    secure_endpoint = "/iast/xcontent-missing-header/test_secure"
    data = {}

    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class Test_XContentSniffing_StackTrace:
    """Validate stack trace generation """

    def setup_stack_trace(self):
        self.r = weblog.get("/iast/xcontent-missing-header/test_insecure")

    def test_stack_trace(self):
        validate_stack_traces(self.r)
