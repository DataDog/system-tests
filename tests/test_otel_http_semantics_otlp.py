# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

"""Validate HTTP OpenTelemetry semantic conventions on the **OTLP export** path
(``DD_TRACE_OTEL_SEMANTICS_ENABLED=true`` + ``OTEL_TRACES_EXPORTER=otlp``, the OTEL_SEMANTICS_OTLP
scenario).

The Datadog agent protocol (v0.4/v0.5) cannot represent OpenTelemetry attribute *types* — every
tag is either a ``meta`` string or a ``metrics`` number. OTLP keeps typed values, so this is the
only path on which we can assert that, per the spec, ``http.response.status_code`` / ``server.port``
are integers and ``http.request.method`` / ``url.*`` / ``error.type`` are strings.

Spec: https://opentelemetry.io/docs/specs/semconv/http/http-spans/
"""

from urllib.parse import urlparse

from utils import features, interfaces, scenarios, weblog
from utils._weblog import HttpResponse
from utils.dd_constants import SpanKind

# Single source of truth for the outbound distant-call target, so the request URL and the
# _http_client_span selector below cannot drift apart.
_DISTANT_CALL_TARGET = "http://weblog:7777/"
_DISTANT_CALL_NETLOC = urlparse(_DISTANT_CALL_TARGET).netloc  # "weblog:7777"


def _server_span(request: HttpResponse) -> dict | None:
    for _, _, span in interfaces.open_telemetry.get_otel_spans(request):
        if span.get("kind") == SpanKind.SERVER.value:
            return span
    return None


def _http_client_span(request: HttpResponse) -> dict | None:
    # get_otel_spans yields the rid-matched SERVER span (it stops at the first match per scope);
    # walk its trace payload for the outbound HTTP CLIENT span to the distant-call target, skipping
    # the OTLP exporter's own client spans (which target the proxy).
    for _, content, _ in interfaces.open_telemetry.get_otel_spans(request):
        for resource_span in content.get("resourceSpans", []):
            for scope_span in resource_span.get("scopeSpans", []):
                for span in scope_span.get("spans", []):
                    attrs = span.get("attributes", {})
                    if span.get("kind") == SpanKind.CLIENT.value and _DISTANT_CALL_NETLOC in str(
                        attrs.get("url.full", "")
                    ):
                        return span
    return None


@features.semantic_core_validations
@scenarios.otel_semantics_otlp
class Test_HttpServerOtelSemanticsOTLP:
    """HTTP server spans exported via OTLP carry the OTel semantic-convention attributes, typed."""

    def setup_attribute_names(self):
        self.r = weblog.get("/")

    def test_attribute_names(self):
        """The OTel attribute names reach the OTLP export (not the Datadog names)."""
        span = _server_span(self.r)
        assert span is not None, "no SERVER span found in the OTLP payload"
        attrs = span["attributes"]

        assert attrs.get("http.request.method") == "GET"
        assert "http.response.status_code" in attrs
        assert attrs.get("url.path") == "/"
        assert attrs.get("url.scheme") in ("http", "https")
        assert "server.address" in attrs
        assert "user_agent.original" in attrs

        for legacy in ("http.method", "http.url", "http.status_code", "http.useragent"):
            assert legacy not in attrs, f"legacy {legacy} tag must be absent in OTel mode"

    def setup_attribute_types(self):
        self.r = weblog.get("/")

    def test_attribute_types(self):
        """String-typed attributes are strings and ``server.port`` is an int (per the spec)."""
        span = _server_span(self.r)
        assert span is not None, "no SERVER span found in the OTLP payload"
        attrs = span["attributes"]

        for key in ("http.request.method", "url.path", "url.scheme", "server.address", "user_agent.original"):
            assert isinstance(attrs.get(key), str), f"{key} must be a string, got {type(attrs.get(key)).__name__}"
        if "server.port" in attrs:
            assert isinstance(attrs["server.port"], int), (
                f"server.port must be an int, got {type(attrs['server.port']).__name__}: {attrs['server.port']!r}"
            )

    def setup_status_code_is_int(self):
        self.r = weblog.get("/")

    def test_status_code_is_int(self):
        """``http.response.status_code`` must be an integer attribute, not a string."""
        span = _server_span(self.r)
        assert span is not None, "no SERVER span found in the OTLP payload"
        status_code = span["attributes"].get("http.response.status_code")
        assert isinstance(status_code, int), (
            f"http.response.status_code must be an int per the spec, got {type(status_code).__name__}: {status_code!r}"
        )
        assert status_code == 200


@features.semantic_core_validations
@scenarios.otel_semantics_otlp
class Test_HttpClientOtelSemanticsOTLP:
    """HTTP client spans exported via OTLP carry the OTel semantic-convention attributes, typed."""

    def setup_attribute_names(self):
        self.r = weblog.get("/make_distant_call", params={"url": _DISTANT_CALL_TARGET})

    def test_attribute_names(self):
        """Client spans use url.full (not the server-only url.path/url.query) with OTel names."""
        span = _http_client_span(self.r)
        assert span is not None, "no HTTP CLIENT span found in the OTLP payload"
        attrs = span["attributes"]

        assert attrs.get("http.request.method") == "GET"
        assert "http.response.status_code" in attrs
        assert attrs.get("url.full"), "client span expects url.full"
        assert "server.address" in attrs
        assert "url.path" not in attrs, "url.path must not be set on client spans"
        assert "url.query" not in attrs, "url.query must not be set on client spans"
        for legacy in ("http.method", "http.url", "http.status_code", "out.host"):
            assert legacy not in attrs, f"legacy {legacy} tag must be absent in OTel mode"

    def setup_attribute_types(self):
        self.r = weblog.get("/make_distant_call", params={"url": _DISTANT_CALL_TARGET})

    def test_attribute_types(self):
        """String-typed attributes are strings and ``server.port`` is an int (per the spec)."""
        span = _http_client_span(self.r)
        assert span is not None, "no HTTP CLIENT span found in the OTLP payload"
        attrs = span["attributes"]

        for key in ("http.request.method", "url.full", "server.address"):
            assert isinstance(attrs.get(key), str), f"{key} must be a string, got {type(attrs.get(key)).__name__}"
        # server.port is Required for client spans; the distant-call URL uses a non-default port.
        assert "server.port" in attrs, "client span expects server.port (Required for client spans)"
        assert isinstance(attrs["server.port"], int), (
            f"server.port must be an int, got {type(attrs['server.port']).__name__}: {attrs['server.port']!r}"
        )

    def setup_status_code_is_int(self):
        self.r = weblog.get("/make_distant_call", params={"url": _DISTANT_CALL_TARGET})

    def test_status_code_is_int(self):
        """``http.response.status_code`` must be an integer attribute, not a string."""
        span = _http_client_span(self.r)
        assert span is not None, "no HTTP CLIENT span found in the OTLP payload"
        status_code = span["attributes"].get("http.response.status_code")
        assert isinstance(status_code, int), (
            f"http.response.status_code must be an int per the spec, got {type(status_code).__name__}: {status_code!r}"
        )
        assert status_code == 200
