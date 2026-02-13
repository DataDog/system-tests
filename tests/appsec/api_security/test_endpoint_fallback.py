# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

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
    """Get a specified span tag from meta"""
    for _, _, span in interfaces.library.get_spans(request=request):
        meta = span.get("meta", {})
        if key in meta:
            return meta[key]
    return None


@rfc("https://docs.google.com/document/d/1GnWwiaw6dkVtgn5f1wcHJETND_Svqd-sJl6FSVVuCkI")
@scenarios.appsec_api_security_with_sampling
@features.api_security_configuration
class Test_Endpoint_Fallback_With_Endpoint:
    """If http.route is absent and http.endpoint is present (non-404), use http.endpoint"""

    def setup_with_endpoint(self):
        self.r1 = weblog.get("/no_route")
        self.r2 = weblog.get("/no_route")

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
        assert endpoint1 == "/no_route", f"Expected http.endpoint to be set, got {endpoint1}"
        assert endpoint2 == "/no_route", f"Expected http.endpoint to be set, got {endpoint2}"

        schema1 = get_schema(self.r1, "res.headers")
        assert schema1 is not None, "Expected schema sampling to occur using http.endpoint"

        schema2 = get_schema(self.r2, "res.headers")
        assert schema2 is None, "Expected no schema sampling on second request (sampling period)"


@rfc("https://docs.google.com/document/d/1GnWwiaw6dkVtgn5f1wcHJETND_Svqd-sJl6FSVVuCkI")
@scenarios.appsec_api_security_with_sampling
@features.api_security_configuration
class Test_Endpoint_Fallback_404:
    """If http.route is absent, http.endpoint is present, but status is 404, should NOT sample"""

    def setup_404(self):
        self.r1 = weblog.get("/not_existing")

    def test_404(self):
        """When status is 404, should not sample even if http.endpoint is present (failsafe)"""
        assert self.r1.status_code == 404

        route1 = get_span_meta(self.r1, "http.route")
        assert route1 is None, f"Expected http.route to be absent, got {route1}"

        endpoint1 = get_span_meta(self.r1, "http.endpoint")
        assert endpoint1 == "/not_existing", f"Expected http.endpoint to be set, got {endpoint1}"

        schema1 = get_schema(self.r1, "res.body")
        assert schema1 is None, "Expected no schema sampling on 404 response (first request)"
