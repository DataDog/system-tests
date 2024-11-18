# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, rfc
from ..utils import BaseSinkTest, validate_stack_traces


@features.iast_sink_untrusted_deserialization
class TestUntrustedDeserialization(BaseSinkTest):
    """Test untrusted deserialization detection."""

    vulnerability_type = "UNTRUSTED_DESERIALIZATION"
    http_method = "GET"
    insecure_endpoint = "/iast/untrusted_deserialization/test_insecure"
    secure_endpoint = "/iast/untrusted_deserialization/test_secure"
    location_map = {"java": "com.datadoghq.system_tests.iast.utils.DeserializationExamples"}


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestUntrustedDeserialization_StackTrace:
    """Validate stack trace generation """

    def setup_stack_trace(self):
        self.r = weblog.get("/iast/untrusted_deserialization/test_insecure")

    def test_stack_trace(self):
        validate_stack_traces(self.r)
