# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, rfc
from ..utils import BaseSinkTestWithoutTelemetry, validate_stack_traces


@features.iast_sink_xpathinjection
class TestXPathInjection(BaseSinkTestWithoutTelemetry):
    """Test xpath injection detection."""

    vulnerability_type = "XPATH_INJECTION"
    http_method = "POST"
    insecure_endpoint = "/iast/xpathi/test_insecure"
    secure_endpoint = "/iast/xpathi/test_secure"
    data = {"expression": "expression"}
    location_map = {"java": "com.datadoghq.system_tests.iast.utils.XPathExamples"}


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestXPathInjection_StackTrace:
    """Validate stack trace generation """

    def setup_stack_trace(self):
        self.r = weblog.post("/iast/xpathi/test_insecure", data={"expression": "expression"})

    def test_stack_trace(self):
        validate_stack_traces(self.r)
