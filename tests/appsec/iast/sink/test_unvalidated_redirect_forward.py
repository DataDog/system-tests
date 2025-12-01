# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, features, missing_feature, rfc, weblog
from tests.appsec.iast.utils import BaseSinkTestWithoutTelemetry, validate_extended_location_data, validate_stack_traces


def _expected_location():
    if context.library.name == "java":
        if context.weblog_variant.startswith("spring-boot"):
            return "com.datadoghq.system_tests.springboot.AppSecIast"
        if context.weblog_variant == "vertx3":
            return "com.datadoghq.vertx3.iast.routes.IastSinkRouteProvider"
        if context.weblog_variant == "vertx4":
            return "com.datadoghq.vertx4.iast.routes.IastSinkRouteProvider"
    return None


@features.iast_sink_unvalidatedforward
class TestUnvalidatedForward(BaseSinkTestWithoutTelemetry):
    """Verify Unvalidated redirect forward detection."""

    vulnerability_type = "UNVALIDATED_REDIRECT"
    http_method = "POST"
    insecure_endpoint = "/iast/unvalidated_redirect/test_insecure_forward"
    secure_endpoint = "/iast/unvalidated_redirect/test_secure_forward"
    data = {"location": "http://dummy.location.com"}
    location_map = _expected_location()

    @missing_feature(library="java", reason="weblog responds 500")
    def test_secure(self):
        super().test_secure()


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestUnvalidatedForward_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.post(
            "/iast/unvalidated_redirect/test_insecure_forward", data={"location": "http://dummy.location.com"}
        )

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class TestUnvalidatedForward_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "UNVALIDATED_REDIRECT"

    def setup_extended_location_data(self):
        self.r = weblog.post(
            "/iast/unvalidated_redirect/test_insecure_forward", data={"location": "http://dummy.location.com"}
        )

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type)
