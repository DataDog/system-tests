# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, rfc
from tests.appsec.iast.utils import (
    BaseSinkTestWithoutTelemetry,
    validate_extended_location_data,
    validate_stack_traces,
    get_nodejs_iast_file_paths,
)


@features.iast_sink_weakrandomness
class TestWeakRandomness(BaseSinkTestWithoutTelemetry):
    """Test weak randomness detection."""

    vulnerability_type = "WEAK_RANDOMNESS"
    http_method = "GET"
    insecure_endpoint = "/iast/weak_randomness/test_insecure"
    secure_endpoint = "/iast/weak_randomness/test_secure"
    data = None
    location_map = {
        "java": "com.datadoghq.system_tests.iast.utils.WeakRandomnessExamples",
        "python": {"flask-poc": "app.py", "django-poc": "app/urls.py"},
        "nodejs": get_nodejs_iast_file_paths(),
    }


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestWeakRandomness_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.get("/iast/weak_randomness/test_insecure")

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class TestWeakRandomness_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "WEAK_RANDOMNESS"

    def setup_extended_location_data(self):
        self.r = weblog.get("/iast/weak_randomness/test_insecure")

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type)
