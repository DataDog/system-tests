# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, irrelevant, features, missing_feature, rfc, weblog
from tests.appsec.iast.utils import BaseSinkTestWithoutTelemetry, validate_extended_location_data, validate_stack_traces


def _expected_location():
    if context.library.name == "java":
        if context.weblog_variant.startswith("spring-boot"):
            return "com.datadoghq.system_tests.springboot.AppSecIast"
        if context.weblog_variant == "resteasy-netty3":
            return "com.datadoghq.resteasy.IastSinkResource"
        if context.weblog_variant == "jersey-grizzly2":
            return "com.datadoghq.jersey.IastSinkResource"
        if context.weblog_variant == "vertx3":
            return "com.datadoghq.vertx3.iast.routes.IastSinkRouteProvider"
        if context.weblog_variant == "vertx4":
            return "com.datadoghq.vertx4.iast.routes.IastSinkRouteProvider"
    if context.library.name == "nodejs":
        if context.weblog_variant in ("express4", "express5"):
            return "iast/index.js"
        if context.weblog_variant == "express4-typescript":
            return "iast.ts"

    return None


@features.iast_sink_unvalidatedredirect
class TestUnvalidatedRedirect(BaseSinkTestWithoutTelemetry):
    """Verify Unvalidated redirect detection."""

    vulnerability_type = "UNVALIDATED_REDIRECT"
    http_method = "POST"
    insecure_endpoint = "/iast/unvalidated_redirect/test_insecure_redirect"
    secure_endpoint = "/iast/unvalidated_redirect/test_secure_redirect"
    data = {"location": "http://dummy.location.com"}
    location_map = _expected_location()

    @irrelevant(library="java", weblog_variant="vertx3", reason="vertx3 redirects using location header")
    def test_insecure(self):
        super().test_insecure()

    # there is probably an issue with how system test handles redirection
    # it's suspicious that three deifferent languages have the same issue
    @irrelevant(library="java", weblog_variant="vertx3", reason="vertx3 redirects using location header")
    @missing_feature(library="dotnet", reason="weblog does not respond")
    @missing_feature(library="java", reason="weblog does not respond")
    @missing_feature(library="nodejs", reason="weblog does not respond")
    def test_secure(self):
        super().test_secure()


@features.iast_sink_unvalidatedheader
class TestUnvalidatedHeader(BaseSinkTestWithoutTelemetry):
    """Verify Unvalidated redirect detection threw header."""

    vulnerability_type = "UNVALIDATED_REDIRECT"
    http_method = "POST"
    insecure_endpoint = "/iast/unvalidated_redirect/test_insecure_header"
    secure_endpoint = "/iast/unvalidated_redirect/test_secure_header"
    data = {"location": "http://dummy.location.com"}
    location_map = _expected_location()

    @missing_feature(context.weblog_variant == "jersey-grizzly2", reason="Endpoint responds 405")
    @missing_feature(context.weblog_variant == "resteasy-netty3", reason="Endpoint responds 405")
    @missing_feature(context.weblog_variant == "vertx3", reason="Endpoint responds 403")
    def test_secure(self):
        return super().test_secure()


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestUnvalidatedRedirect_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.post(
            "/iast/unvalidated_redirect/test_insecure_redirect", data={"location": "http://dummy.location.com"}
        )

    @irrelevant(library="java", weblog_variant="vertx3", reason="vertx3 redirects using location header")
    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class TestUnvalidatedHeader_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.post(
            "/iast/unvalidated_redirect/test_insecure_header", data={"location": "http://dummy.location.com"}
        )

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class TestUnvalidatedRedirect_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "UNVALIDATED_REDIRECT"

    def setup_extended_location_data(self):
        self.r = weblog.post(
            "/iast/unvalidated_redirect/test_insecure_redirect", data={"location": "http://dummy.location.com"}
        )

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class TestUnvalidatedHeader_ExtendedLocation:
    """Test extended location data"""

    vulnerability_type = "UNVALIDATED_REDIRECT"

    def setup_extended_location_data(self):
        self.r = weblog.post(
            "/iast/unvalidated_redirect/test_insecure_header", data={"location": "http://dummy.location.com"}
        )

    def test_extended_location_data(self):
        validate_extended_location_data(self.r, self.vulnerability_type)
