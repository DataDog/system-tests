# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, rfc
from tests.appsec.iast.utils import BaseSinkTestWithoutTelemetry, validate_extended_location_data, validate_stack_traces


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
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.post("/iast/xpathi/test_insecure", data={"expression": "expression"})

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class TestXPathInjection_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "XPATH_INJECTION"

    def setup_extended_location_data(self):
        self.r = weblog.post("/iast/xpathi/test_insecure", data={"expression": "expression"})

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type)
