# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, features, rfc, weblog
from tests.appsec.iast.utils import BaseSinkTest, validate_extended_location_data, validate_stack_traces


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
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.get("/iast/xcontent-missing-header/test_insecure")

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class Test_XContentSniffing_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "XCONTENTTYPE_HEADER_MISSING"

    def setup_extended_location_data(self):
        self.r = weblog.get("/iast/xcontent-missing-header/test_insecure")

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type, is_expected_location_required=False)
