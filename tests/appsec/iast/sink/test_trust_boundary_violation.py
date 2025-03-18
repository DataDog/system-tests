# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features, rfc, weblog
from tests.appsec.iast.utils import BaseSinkTest, validate_extended_location_data, validate_stack_traces


@features.iast_sink_trustboundaryviolation
class Test_TrustBoundaryViolation(BaseSinkTest):
    """Test Trust Boundary Violation detection."""

    vulnerability_type = "TRUST_BOUNDARY_VIOLATION"
    http_method = "GET"
    insecure_endpoint = "/iast/trust-boundary-violation/test_insecure"
    secure_endpoint = "/iast/trust-boundary-violation/test_secure"
    params = {"username": "shaquille_oatmeal", "password": "123456"}

    @missing_feature(library="nodejs", reason="Metrics implemented")
    @missing_feature(library="dotnet", reason="Metrics implemented")
    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(library="nodejs", reason="Metrics implemented")
    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class Test_TrustBoundaryViolation_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.get(
            "/iast/trust-boundary-violation/test_insecure",
            params={"username": "shaquille_oatmeal", "password": "123456"},
        )

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class Test_TrustBoundaryViolation_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "TRUST_BOUNDARY_VIOLATION"

    def setup_extended_location_data(self):
        self.r = weblog.get(
            "/iast/trust-boundary-violation/test_insecure",
            params={"username": "shaquille_oatmeal", "password": "123456"},
        )

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type, is_expected_location_required=True)
