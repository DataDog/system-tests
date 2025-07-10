# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, missing_feature, bug, weblog, features, rfc, scenarios, flaky
from tests.appsec.iast.utils import (
    BaseSinkTest,
    BaseTestCookieNameFilter,
    validate_extended_location_data,
    validate_stack_traces,
    get_nodejs_iast_file_paths,
)


@features.iast_sink_insecure_cookie
class TestInsecureCookie(BaseSinkTest):
    """Test insecure cookie detection."""

    vulnerability_type = "INSECURE_COOKIE"
    http_method = "GET"
    insecure_endpoint = "/iast/insecure-cookie/test_insecure"
    secure_endpoint = "/iast/insecure-cookie/test_secure"
    data = {}
    location_map = {
        "nodejs": get_nodejs_iast_file_paths(),
    }

    @bug(context.library < "java@1.18.3", reason="APMRP-360")
    def test_secure(self):
        super().test_secure()

    def setup_empty_cookie(self):
        self.request_empty_cookie = weblog.get("/iast/insecure-cookie/test_empty_cookie")

    def test_empty_cookie(self):
        self.assert_no_iast_event(self.request_empty_cookie)

    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    @missing_feature(context.library < "python@3.1.0", reason="Metrics not implemented")
    @missing_feature(library="dotnet", reason="Metrics not implemented")
    def test_telemetry_metric_instrumented_sink(self):
        super().test_telemetry_metric_instrumented_sink()

    @missing_feature(context.library < "java@1.22.0", reason="Metrics not implemented")
    @flaky(weblog_variant="vertx4", reason="APPSEC-56453")
    def test_telemetry_metric_executed_sink(self):
        super().test_telemetry_metric_executed_sink()


@features.iast_sink_insecure_cookie
@scenarios.iast_deduplication
class TestInsecureCookieNameFilter(BaseTestCookieNameFilter):
    """Test no SameSite cookie name filter."""

    vulnerability_type = "INSECURE_COOKIE"
    endpoint = "/iast/insecure-cookie/custom_cookie"


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestInsecureCookie_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.get("/iast/insecure-cookie/test_insecure")

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class TestInsecureCookie_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "INSECURE_COOKIE"

    def setup_extended_location_data(self):
        self.r = weblog.get("/iast/insecure-cookie/test_insecure")

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type)
