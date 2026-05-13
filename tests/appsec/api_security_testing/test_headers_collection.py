# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

import json

from utils import interfaces, rfc, weblog, features, scenarios
from utils._weblog import HttpResponse


@rfc("https://docs.google.com/document/d/1uR4QQvU8pItEV2zFqr3-L6jO2jxzmvLrFTX_yyvqIOA")
@features.api_security_testing_headers_collection
@scenarios.default
@scenarios.everything_disabled
@scenarios.library_conf_custom_header_tags
class Test_SecurityTestingHeaders:
    """Tracers tag the x-datadog-endpoint-scan and x-datadog-security-test request headers
    on service entry spans as http.request.headers.<name> unconditionally (regardless of
    DD_TRACE_HEADER_TAGS or AppSec being enabled) and do not propagate them downstream.

    Stacking three scenarios covers the unconditional contract:
      - @scenarios.default: AppSec on
      - @scenarios.everything_disabled: AppSec off
      - @scenarios.library_conf_custom_header_tags: AppSec on, DD_TRACE_HEADER_TAGS set to
        unrelated header configs (header1..header6) so a tracer that only honors these
        markers when DD_TRACE_HEADER_TAGS is unset still has to pass.
    """

    SCAN_VALUE = "scan-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    TEST_VALUE = "test-bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    HEADERS = {
        "x-datadog-endpoint-scan": SCAN_VALUE,
        "x-datadog-security-test": TEST_VALUE,
    }

    @staticmethod
    def _assert_collected(response: HttpResponse) -> None:
        # Positive check used by every test so the whole class fails when a tracer has
        # not implemented the RFC, instead of an absence/non-propagation test silently passing.
        assert response.status_code == 200
        span = interfaces.library.get_root_span(request=response)
        meta = span.get("meta", {}) or {}
        assert meta.get("http.request.headers.x-datadog-endpoint-scan") == Test_SecurityTestingHeaders.SCAN_VALUE, (
            "http.request.headers.x-datadog-endpoint-scan not collected on entry span"
        )
        assert meta.get("http.request.headers.x-datadog-security-test") == Test_SecurityTestingHeaders.TEST_VALUE, (
            "http.request.headers.x-datadog-security-test not collected on entry span"
        )

    @staticmethod
    def _outgoing_header_keys(request_headers: dict | list) -> set[str]:
        # /make_distant_call returns the outbound request headers either as a dict or as a list
        # of {key, value} objects depending on the weblog implementation (see extract_baggage_value
        # in tests/test_baggage.py for the same dual-shape pattern). Returns lowercased keys.
        if isinstance(request_headers, dict):
            return {k.lower() for k in request_headers}
        return {h.get("key", "").lower() for h in request_headers}

    def setup_collected_when_present(self):
        self.r_collected = weblog.get("/waf", headers=self.HEADERS)

    def test_collected_when_present(self):
        """Both headers are tagged on the entry span as http.request.headers.<name>."""
        self._assert_collected(self.r_collected)

    def setup_absent_when_not_in_request(self):
        self.r_collected = weblog.get("/waf", headers=self.HEADERS)
        self.r_without_headers = weblog.get("/waf")

    def test_absent_when_not_in_request(self):
        """No security testing tag is set when the headers are not in the request."""
        self._assert_collected(self.r_collected)
        assert self.r_without_headers.status_code == 200
        span = interfaces.library.get_root_span(request=self.r_without_headers)
        meta = span.get("meta", {}) or {}
        assert meta.get("http.request.headers.x-datadog-endpoint-scan") is None
        assert meta.get("http.request.headers.x-datadog-security-test") is None

    def setup_not_propagated_downstream(self):
        self.r_distant = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777/"},
            headers=self.HEADERS,
        )

    def test_not_propagated_downstream(self):
        """The security testing headers must not be propagated to downstream services.

        Asserts directly on the outbound request headers reported back by /make_distant_call,
        rather than counting tagged spans across the distributed trace -- the latter false-passes
        when the inner request ends up in a separate trace. The positive collection check is also
        done on this request so an endpoint-specific regression on /make_distant_call (tagging on
        /waf but not here) is caught.
        """
        self._assert_collected(self.r_distant)
        outgoing = self._outgoing_header_keys(json.loads(self.r_distant.text).get("request_headers") or {})
        assert "x-datadog-endpoint-scan" not in outgoing, (
            f"x-datadog-endpoint-scan was propagated to downstream request: {outgoing}"
        )
        assert "x-datadog-security-test" not in outgoing, (
            f"x-datadog-security-test was propagated to downstream request: {outgoing}"
        )
