# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, rfc
from tests.appsec.iast.utils import (
    BaseSinkTest,
    validate_extended_location_data,
    validate_stack_traces,
    get_nodejs_iast_file_paths,
)


@features.iast_sink_untrusted_deserialization
class TestUntrustedDeserialization(BaseSinkTest):
    """Test untrusted deserialization detection."""

    vulnerability_type = "UNTRUSTED_DESERIALIZATION"
    http_method = "GET"
    insecure_endpoint = "/iast/untrusted_deserialization/test_insecure?name=example"
    secure_endpoint = "/iast/untrusted_deserialization/test_secure"
    location_map = {
        "java": "com.datadoghq.system_tests.iast.utils.DeserializationExamples",
        "nodejs": get_nodejs_iast_file_paths(),
    }


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestUntrustedDeserialization_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.get("/iast/untrusted_deserialization/test_insecure?name=example")

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class TestUntrustedDeserialization_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "UNTRUSTED_DESERIALIZATION"

    def setup_extended_location_data(self):
        self.r = weblog.get("/iast/untrusted_deserialization/test_insecure?name=example")

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type)
