# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Test RFC-1076: API Security sampling when tracers lack HTTP routes (http.route)

This tests the fallback chain for determining the sampling key when http.route is not available:
1. Use http.route if present (preferred)
2. If absent, use http.endpoint if present and status != 404
3. If both absent, compute endpoint from http.url (don't set it on span)
"""

from utils import interfaces, rfc, scenarios, weblog, features
from utils._weblog import HttpResponse


def get_schema(request: HttpResponse, address: str):
    """Get api security schema from spans"""
    for _, _, span in interfaces.library.get_spans(request):
        meta = span.get("meta", {})
        payload = meta.get("_dd.appsec.s." + address)
        if payload is not None:
            return payload
    return None


def get_span_meta(request: HttpResponse, key: str):
    """Get a specific meta value from the root span"""
    span = interfaces.library.get_root_span(request)
    return span.get("meta", {}).get(key)


@rfc("https://docs.google.com/document/d/1GnWwiaw6dkVtgn5f1wcHJETND_Svqd-sJl6FSVVuCkI")
@scenarios.appsec_api_security_with_sampling
@features.api_security_configuration
class Test_Endpoint_Fallback_With_Route:
    """Test Requirement 1: If http.route is present, use it for sampling"""

    def setup_with_route(self):
        self.r1 = weblog.get("/endpoint_fallback?case=with_route")
        self.r2 = weblog.get("/endpoint_fallback?case=with_route")

    def test_with_route(self):
        """When http.route is present, it should be used for sampling"""
        assert self.r1.status_code == 200
        assert self.r2.status_code == 200

        route1 = get_span_meta(self.r1, "http.route")
        route2 = get_span_meta(self.r2, "http.route")
        assert route1 == "/users/{id}/profile", f"Expected http.route to be set, got {route1}"
        assert route2 == "/users/{id}/profile", f"Expected http.route to be set, got {route2}"

        schema1 = get_schema(self.r1, "res.body")
        assert schema1 is not None, "Expected schema sampling to occur on first request"

        schema2 = get_schema(self.r2, "res.body")
        assert schema2 is None, "Expected no schema sampling on second request (sampling period)"


@rfc("https://docs.google.com/document/d/1GnWwiaw6dkVtgn5f1wcHJETND_Svqd-sJl6FSVVuCkI")
@scenarios.appsec_api_security_with_sampling
@features.api_security_configuration
class Test_Endpoint_Fallback_With_Endpoint:
    """Test Requirement 2a: If http.route is absent and http.endpoint is present (non-404), use http.endpoint"""

    def setup_with_endpoint(self):
        self.r1 = weblog.get("/endpoint_fallback?case=with_endpoint")
        self.r2 = weblog.get("/endpoint_fallback?case=with_endpoint")

    def test_with_endpoint(self):
        """When http.route is absent but http.endpoint is present, use http.endpoint for sampling"""
        assert self.r1.status_code == 200
        assert self.r2.status_code == 200

        route1 = get_span_meta(self.r1, "http.route")
        route2 = get_span_meta(self.r2, "http.route")
        assert route1 is None, f"Expected http.route to be absent, got {route1}"
        assert route2 is None, f"Expected http.route to be absent, got {route2}"

        endpoint1 = get_span_meta(self.r1, "http.endpoint")
        endpoint2 = get_span_meta(self.r2, "http.endpoint")
        assert endpoint1 == "/api/products/{param:int}", f"Expected http.endpoint to be set, got {endpoint1}"
        assert endpoint2 == "/api/products/{param:int}", f"Expected http.endpoint to be set, got {endpoint2}"

        schema1 = get_schema(self.r1, "res.body")
        assert schema1 is not None, "Expected schema sampling to occur using http.endpoint"

        schema2 = get_schema(self.r2, "res.body")
        assert schema2 is None, "Expected no schema sampling on second request (sampling period)"


@rfc("https://docs.google.com/document/d/1GnWwiaw6dkVtgn5f1wcHJETND_Svqd-sJl6FSVVuCkI")
@scenarios.appsec_api_security_with_sampling
@features.api_security_configuration
class Test_Endpoint_Fallback_404:
    """Test Requirement 2b: If http.route is absent, http.endpoint is present, but status is 404, should NOT sample"""

    def setup_404(self):
        self.r1 = weblog.get("/endpoint_fallback?case=404")

    def test_404(self):
        """When status is 404, should not sample even if http.endpoint is present (failsafe)"""
        assert self.r1.status_code == 404

        route1 = get_span_meta(self.r1, "http.route")
        assert route1 is None, f"Expected http.route to be absent, got {route1}"

        endpoint1 = get_span_meta(self.r1, "http.endpoint")
        assert endpoint1 == "/api/notfound/{param:int}", f"Expected http.endpoint to be set, got {endpoint1}"

        schema1 = get_schema(self.r1, "res.body")
        assert schema1 is None, "Expected no schema sampling on 404 response (first request)"


@rfc("https://docs.google.com/document/d/1GnWwiaw6dkVtgn5f1wcHJETND_Svqd-sJl6FSVVuCkI")
@scenarios.appsec_api_security_with_sampling
@features.api_security_configuration
class Test_Endpoint_Fallback_Computed:
    """Test Requirement 3: If neither http.route nor http.endpoint present, compute endpoint on-demand"""

    def setup_computed(self):
        self.r1 = weblog.get("/endpoint_fallback?case=computed")

    def test_computed(self):
        """When neither http.route nor http.endpoint are set, compute endpoint but don't set it on span"""
        assert self.r1.status_code == 200

        route1 = get_span_meta(self.r1, "http.route")
        assert route1 is None, f"Expected http.route to be absent, got {route1}"

        endpoint1 = get_span_meta(self.r1, "http.endpoint")
        assert endpoint1 is None, f"Expected http.endpoint to NOT be set on span, got {endpoint1}"

        url1 = get_span_meta(self.r1, "http.url")
        assert url1 is not None
        assert "/endpoint_fallback_computed/users/123/orders/456" in url1

        schema1 = get_schema(self.r1, "res.body")
        assert schema1 is not None, "Expected schema sampling to occur using computed endpoint"
