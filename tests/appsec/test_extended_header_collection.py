# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, scenarios, rfc, features, missing_feature, context


@rfc("https://docs.google.com/document/d/1indvMPy4RSFeEurxssXMHUfmw6BlCexqJD_IVM6Vw9w")
@features.appsec_collect_all_headers
@scenarios.appsec_standalone
class Test_ExtendedHeaderCollection:
    @staticmethod
    def assert_feature_is_enabled(response) -> None:
        assert response.status_code == 200
        span = interfaces.library.get_root_span(request=response)
        meta = span.get("meta", {})
        assert meta.get("http.request.headers.x-my-header-1") == "value1"

    def setup_feature_is_enabled(self):
        self.check_r = weblog.get(
            "/headers",
            headers={
                "User-Agent": "Arachni/v1",  # triggers appsec event
                "X-My-Header-1": "value1",
            },
        )

    def setup_if_appsec_event_collect_all_request_headers(self):
        self.r = weblog.get(
            "/headers",
            headers={
                "User-Agent": "Arachni/v1",  # triggers appsec event
                "X-My-Header-1": "value1",
                "X-My-Header-2": "value2",
                "X-My-Header-3": "value3",
                "X-My-Header-4": "value4",
                "Content-Type": "text/html",
            },
        )

    def test_if_appsec_event_collect_all_request_headers(self):
        assert self.r.status_code == 200
        span = interfaces.library.get_root_span(request=self.r)
        meta = span.get("meta", {})
        assert meta.get("http.request.headers.x-my-header-1") == "value1"
        assert meta.get("http.request.headers.x-my-header-2") == "value2"
        assert meta.get("http.request.headers.x-my-header-3") == "value3"
        assert meta.get("http.request.headers.x-my-header-4") == "value4"
        assert meta.get("http.request.headers.content-type") == "text/html"
        metrics = span.get("metrics", {})
        assert metrics.get("_dd.appsec.request.header_collection.discarded") is None

    def setup_if_no_appsec_event_collect_allowed_request_headers(self):
        self.setup_feature_is_enabled()
        self.r = weblog.get(
            "/headers",
            headers={
                "X-My-Header-1": "value1",
                "X-My-Header-2": "value2",
                "X-My-Header-3": "value3",
                "X-My-Header-4": "value4",
                "Content-Type": "text/html",
            },
        )

    def test_if_no_appsec_event_collect_allowed_request_headers(self):
        self.assert_feature_is_enabled(self.check_r)
        assert self.r.status_code == 200
        span = interfaces.library.get_root_span(request=self.r)
        meta = span.get("meta", {})
        assert meta.get("http.request.headers.x-my-header-1") is None
        assert meta.get("http.request.headers.x-my-header-2") is None
        assert meta.get("http.request.headers.x-my-header-3") is None
        assert meta.get("http.request.headers.x-my-header-4") is None
        assert meta.get("http.request.headers.content-type") == "text/html"
        metrics = span.get("metrics", {})
        assert metrics.get("_dd.appsec.request.header_collection.discarded") is None

    def setup_not_exceed_default_50_maximum_request_header_collection(self):
        self.setup_feature_is_enabled()
        # Generate 100 headers with the pattern "X-My-Header-<n>": "value<n>"
        headers = {f"X-My-Header-{i}": f"value{i}" for i in range(1, 51)}
        headers = {
            **headers,
            "User-Agent": "Arachni/v1",  # triggers appsec event
            "Content-Type": "text/html",
        }
        self.r = weblog.get("/headers", headers=headers)

    def test_not_exceed_default_50_maximum_request_header_collection(self):
        self.assert_feature_is_enabled(self.check_r)
        assert self.r.status_code == 200
        span = interfaces.library.get_root_span(request=self.r)
        meta = span.get("meta", {})

        # Ensure no more than 50 meta entries start with "http.request.headers."
        header_keys = [k for k in meta if k.startswith("http.request.headers.")]
        assert len(header_keys) <= 50, f"Expected at most 50 collected headers, got {len(header_keys)}: {header_keys}"

        # Ensure allowed headers are collected
        assert meta.get("http.request.headers.content-type") == "text/html"

        metrics = span.get("metrics", {})
        # Confirm _dd.appsec.request.header_collection.discarded exists and is > 0
        discarded = metrics.get("_dd.appsec.request.header_collection.discarded")
        assert discarded is not None
        assert discarded > 0

    def setup_if_appsec_event_collect_all_response_headers(self):
        self.r = weblog.get(
            "/customResponseHeaders",
            headers={
                "User-Agent": "Arachni/v1"  # triggers appsec event
            },
        )

    @missing_feature(context.weblog_variant == "fastify", reason="Collecting reply headers not supported yet")
    def test_if_appsec_event_collect_all_response_headers(self):
        assert self.r.status_code == 200
        span = interfaces.library.get_root_span(request=self.r)
        meta = span.get("meta", {})
        assert meta.get("http.response.headers.x-test-header-1") == "value1"
        assert meta.get("http.response.headers.x-test-header-2") == "value2"
        assert meta.get("http.response.headers.x-test-header-3") == "value3"
        assert meta.get("http.response.headers.x-test-header-4") == "value4"
        assert meta.get("http.response.headers.x-test-header-5") == "value5"
        assert meta.get("http.response.headers.content-language") == "en-US"
        metrics = span.get("metrics", {})
        assert metrics.get("_dd.appsec.response.header_collection.discarded") is None

    def setup_if_no_appsec_event_collect_allowed_response_headers(self):
        self.setup_feature_is_enabled()
        self.r = weblog.get("/customResponseHeaders")

    def test_if_no_appsec_event_collect_allowed_response_headers(self):
        self.assert_feature_is_enabled(self.check_r)
        assert self.r.status_code == 200
        span = interfaces.library.get_root_span(request=self.r)
        meta = span.get("meta", {})
        assert meta.get("http.response.headers.x-test-header-1") is None
        assert meta.get("http.response.headers.x-test-header-2") is None
        assert meta.get("http.response.headers.x-test-header-3") is None
        assert meta.get("http.response.headers.x-test-header-4") is None
        assert meta.get("http.response.headers.x-test-header-5") is None
        assert (
            meta.get("http.response.headers.content-language") is None
        )  # at least in java we are not collecting response headers by default
        metrics = span.get("metrics", {})
        assert metrics.get("_dd.appsec.response.header_collection.discarded") is None

    def setup_not_exceed_default_50_maximum_response_header_collection(self):
        self.setup_feature_is_enabled()
        self.r = weblog.get(
            "/exceedResponseHeaders",
            headers={
                "User-Agent": "Arachni/v1"  # triggers appsec event
            },
        )

    @missing_feature(context.weblog_variant == "fastify", reason="Collecting reply headers not supported yet")
    def test_not_exceed_default_50_maximum_response_header_collection(self):
        self.assert_feature_is_enabled(self.check_r)
        assert self.r.status_code == 200
        span = interfaces.library.get_root_span(request=self.r)
        meta = span.get("meta", {})

        # Ensure no more than 50 meta entries start with "http.request.headers."
        header_keys = [k for k in meta if k.startswith("http.response.headers.")]
        assert len(header_keys) <= 50, f"Expected at most 50 collected headers, got {len(header_keys)}: {header_keys}"

        # Ensure allowed headers are collected
        assert meta.get("http.response.headers.content-language") == "en-US"

        metrics = span.get("metrics", {})
        # Confirm _dd.appsec.response.header_collection.discarded exists and is > 0
        discarded = metrics.get("_dd.appsec.response.header_collection.discarded")
        assert discarded is not None
        assert discarded > 0
