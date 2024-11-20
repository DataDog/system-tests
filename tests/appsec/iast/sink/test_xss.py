# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, rfc
from ..utils import BaseSinkTestWithoutTelemetry, validate_stack_traces


@features.iast_sink_xss
class TestXSS(BaseSinkTestWithoutTelemetry):
    """Test xss detection."""

    vulnerability_type = "XSS"
    http_method = "POST"
    insecure_endpoint = "/iast/xss/test_insecure"
    secure_endpoint = "/iast/xss/test_secure"
    data = {"param": "param"}
    location_map = {"java": "com.datadoghq.system_tests.iast.utils.XSSExamples"}


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestXSS_StackTrace:
    """Validate stack trace generation """

    def setup_stack_trace(self):
        self.r = weblog.post("/iast/xss/test_insecure", data={"param": "param"})

    def test_stack_trace(self):
        validate_stack_traces(self.r)
