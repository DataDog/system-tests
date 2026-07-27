# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

"""OpenTelemetry HTTP semantic-convention system tests.

The behavior tests run over both supported transports:

* ``OTEL_SEMANTICS`` validates the tracer-to-Agent payload.
* ``OTEL_SEMANTICS_OTLP`` validates the direct OTLP export.

Transport-specific helpers below normalize those payloads so every semantic assertion is
identical on both paths. OTLP-only tests additionally validate attribute value types and
custom error-status configuration.

Specification: https://opentelemetry.io/docs/specs/semconv/http/http-spans/
"""

from collections.abc import Iterator
from typing import Any

from utils import context, features, interfaces, rfc, scenarios, weblog
from utils._weblog import HttpResponse
from utils.dd_constants import SpanKind, StatusCode
from utils.dd_types import DataDogLibrarySpan


type HttpSpan = DataDogLibrarySpan | dict[str, Any]

_DISTANT_CALL_TARGET = "http://weblog:7777/"
_SENSITIVE_QUERY_VALUE = "otel-sensitive-value"
_CLIENT_ADDRESS = "203.0.113.42"


def _is_otlp_scenario() -> bool:
    return context.scenario in (
        scenarios.otel_semantics_otlp,
        scenarios.otel_semantics_otlp_custom_error_statuses,
    )


def _attributes(span: HttpSpan) -> dict[str, Any]:
    if isinstance(span, DataDogLibrarySpan):
        return {**span.meta, **span.metrics}
    return span.get("attributes", {})


def _span_name(span: HttpSpan) -> str:
    if isinstance(span, DataDogLibrarySpan):
        return str(span["resource"])
    return str(span["name"])


def _span_is_error(span: HttpSpan) -> bool:
    if isinstance(span, DataDogLibrarySpan):
        return int(span.get("error", 0) or 0) == 1

    status = span.get("status", {})
    return int(status.get("code", StatusCode.STATUS_CODE_UNSET.value)) == StatusCode.STATUS_CODE_ERROR.value


def _iter_otlp_spans(request: HttpResponse) -> Iterator[dict[str, Any]]:
    """Yield every span in the first OTLP payload associated with ``request``."""
    for _, content, _ in interfaces.open_telemetry.get_otel_spans(request):
        for resource_span in content.get("resourceSpans", []):
            for scope_span in resource_span.get("scopeSpans", []):
                yield from scope_span.get("spans", [])
        return


def _server_span(request: HttpResponse) -> HttpSpan:
    if _is_otlp_scenario():
        request_id = request.get_rid()
        fallback: dict[str, Any] | None = None
        for span in _iter_otlp_spans(request):
            if span.get("kind") != SpanKind.SERVER.value:
                continue
            if fallback is None:
                fallback = span
            user_agent = str(_attributes(span).get("user_agent.original", ""))
            if request_id in user_agent:
                return span
        assert fallback is not None, "no SERVER span found in the OTLP payload"
        return fallback

    spans = [span for _, _, span in interfaces.library.get_spans(request)]
    assert spans, "no server span found in the tracer payload"
    assert len(spans) == 1, f"expected one request-correlated server span, found {len(spans)}"
    return spans[0]


def _client_span(request: HttpResponse) -> HttpSpan:
    if _is_otlp_scenario():
        spans: Iterator[HttpSpan] = _iter_otlp_spans(request)
    else:
        spans = (span for _, _, span in interfaces.library.get_spans(request, full_trace=True))

    for span in spans:
        attrs = _attributes(span)
        if isinstance(span, DataDogLibrarySpan):
            is_client = attrs.get("span.kind") == "client"
        else:
            is_client = span.get("kind") == SpanKind.CLIENT.value

        if is_client and (attrs.get("server.address") == "weblog" or "weblog:7777" in str(attrs.get("url.full", ""))):
            return span

    raise AssertionError("no HTTP CLIENT span to weblog:7777 found")


def _distant_call(target: str = _DISTANT_CALL_TARGET, *, method: str = "GET") -> HttpResponse:
    return weblog.get("/make_distant_call", params={"url": target, "method": method})


def _assert_status_error(span: HttpSpan, status_code: int) -> None:
    attrs = _attributes(span)
    assert attrs.get("http.response.status_code") == status_code
    assert _span_is_error(span), f"HTTP {status_code} span must be marked as an error"
    assert attrs.get("error.type") == str(status_code)


def _assert_status_not_error(span: HttpSpan, status_code: int) -> None:
    attrs = _attributes(span)
    assert attrs.get("http.response.status_code") == status_code
    assert not _span_is_error(span), f"HTTP {status_code} span must not be marked as an error"
    assert "error.type" not in attrs


@rfc("https://docs.google.com/document/d/1SONUGEa38eLumE5b6gnNhykFhzZL9uQpsnMFq06uDMY/edit")
@features.semantic_core_validations
@scenarios.otel_semantics
@scenarios.otel_semantics_otlp
class Test_OtelSemantics_Spans_Http_Server:
    """HTTP server spans use OTel names, values, naming, and status semantics."""

    def setup_otel_attributes_present(self) -> None:
        self.response = weblog.get("/")

    def test_otel_attributes_present(self) -> None:
        attrs = _attributes(_server_span(self.response))
        assert attrs.get("http.request.method") == "GET"
        assert attrs.get("url.path") == "/"
        assert attrs.get("url.scheme") in ("http", "https")
        assert attrs.get("http.response.status_code") == 200

    def setup_legacy_attributes_absent(self) -> None:
        self.response = weblog.get("/", headers={"X-Forwarded-For": _CLIENT_ADDRESS})

    def test_legacy_attributes_absent(self) -> None:
        attrs = _attributes(_server_span(self.response))
        for legacy in ("http.method", "http.url", "http.status_code", "http.useragent", "http.client_ip"):
            assert legacy not in attrs

    def setup_span_name_with_route(self) -> None:
        self.response = weblog.get("/sample_rate_route/1")

    def test_span_name_with_route(self) -> None:
        span = _server_span(self.response)
        route = _attributes(span).get("http.route")
        assert route
        assert route != "/sample_rate_route/1", "http.route must be a low-cardinality route template"
        assert _span_name(span) == f"GET {route}"

    def setup_span_name_without_route(self) -> None:
        self.response = weblog.get("/no_such_route_xyz")

    def test_span_name_without_route(self) -> None:
        span = _server_span(self.response)
        assert _span_name(span) == "GET"
        assert "no_such_route_xyz" not in _span_name(span)

    def setup_span_name_unknown_method(self) -> None:
        # Node's HTTP parser rejects arbitrary tokens before instrumentation can see them.
        # PROPFIND is accepted on the wire but is outside the RFC 9110 + PATCH + QUERY allowlist.
        self.response = weblog.request("PROPFIND", "/")

    def test_span_name_unknown_method(self) -> None:
        span = _server_span(self.response)
        attrs = _attributes(span)
        assert attrs.get("http.request.method") == "_OTHER"
        assert attrs.get("http.request.method_original") == "PROPFIND"
        assert _span_name(span) == "HTTP"

    def setup_status_500_no_exception_is_status_code_error(self) -> None:
        self.response = weblog.get("/status", params={"code": "500"})

    def test_status_500_no_exception_is_status_code_error(self) -> None:
        _assert_status_error(_server_span(self.response), 500)

    def setup_status_400_is_not_error(self) -> None:
        self.response = weblog.get("/status", params={"code": "400"})

    def test_status_400_is_not_error(self) -> None:
        _assert_status_not_error(_server_span(self.response), 400)

    def setup_status_3xx_is_not_error(self) -> None:
        self.response = weblog.get("/status", params={"code": "302"}, allow_redirects=False)

    def test_status_3xx_is_not_error(self) -> None:
        _assert_status_not_error(_server_span(self.response), 302)

    def setup_url_query_present_with_query_string(self) -> None:
        self.response = weblog.get("/", params={"otel": "visible"})

    def test_url_query_present_with_query_string(self) -> None:
        query = _attributes(_server_span(self.response)).get("url.query")
        assert query == "otel=visible"

    def setup_url_query_absent_without_query_string(self) -> None:
        self.response = weblog.get("/")

    def test_url_query_absent_without_query_string(self) -> None:
        assert "url.query" not in _attributes(_server_span(self.response))

    def setup_url_query_obfuscation(self) -> None:
        self.response = weblog.get("/", params={"token": _SENSITIVE_QUERY_VALUE})

    def test_url_query_obfuscation(self) -> None:
        query = str(_attributes(_server_span(self.response)).get("url.query", ""))
        assert "token=" in query
        assert _SENSITIVE_QUERY_VALUE not in query
        assert "redacted" in query.lower()

    def setup_user_agent(self) -> None:
        self.response = weblog.get("/")

    def test_user_agent(self) -> None:
        attrs = _attributes(_server_span(self.response))
        assert attrs.get("user_agent.original")
        assert "http.useragent" not in attrs

    def setup_client_address(self) -> None:
        self.response = weblog.get("/", headers={"X-Forwarded-For": _CLIENT_ADDRESS})

    def test_client_address(self) -> None:
        attrs = _attributes(_server_span(self.response))
        assert attrs.get("client.address") == _CLIENT_ADDRESS
        assert "http.client_ip" not in attrs

    def setup_network_peer_address(self) -> None:
        self.response = weblog.get("/")

    def test_network_peer_address(self) -> None:
        attrs = _attributes(_server_span(self.response))
        assert attrs.get("network.peer.address")
        assert "network.client.ip" not in attrs

    def setup_server_address(self) -> None:
        self.response = weblog.get("/")

    def test_server_address(self) -> None:
        attrs = _attributes(_server_span(self.response))
        assert attrs.get("server.address")
        assert "http.hostname" not in attrs

    def setup_http_route_retained(self) -> None:
        self.response = weblog.get("/sample_rate_route/1")

    def test_http_route_retained(self) -> None:
        route = _attributes(_server_span(self.response)).get("http.route")
        assert route
        assert route != "/sample_rate_route/1", "http.route must be a low-cardinality route template"


@rfc("https://docs.google.com/document/d/1SONUGEa38eLumE5b6gnNhykFhzZL9uQpsnMFq06uDMY/edit")
@features.semantic_core_validations
@scenarios.otel_semantics
@scenarios.otel_semantics_otlp
class Test_OtelSemantics_Spans_Http_Client:
    """HTTP client spans use OTel names, values, naming, and status semantics."""

    def setup_otel_attributes_present(self) -> None:
        self.response = _distant_call()

    def test_otel_attributes_present(self) -> None:
        attrs = _attributes(_client_span(self.response))
        assert attrs.get("http.request.method") == "GET"
        assert attrs.get("url.full") == _DISTANT_CALL_TARGET
        assert attrs.get("server.address") == "weblog"
        assert attrs.get("server.port") == 7777
        assert attrs.get("http.response.status_code") == 200

    def setup_legacy_attributes_absent(self) -> None:
        self.response = _distant_call()

    def test_legacy_attributes_absent(self) -> None:
        attrs = _attributes(_client_span(self.response))
        for legacy in ("http.method", "http.url", "out.host", "peer.hostname"):
            assert legacy not in attrs

    def setup_span_name_is_method(self) -> None:
        self.response = _distant_call()

    def test_span_name_is_method(self) -> None:
        assert _span_name(_client_span(self.response)) == "GET"

    def setup_span_name_unknown_method(self) -> None:
        self.response = _distant_call(method="PROPFIND")

    def test_span_name_unknown_method(self) -> None:
        span = _client_span(self.response)
        attrs = _attributes(span)
        assert attrs.get("http.request.method") == "_OTHER"
        assert attrs.get("http.request.method_original") == "PROPFIND"
        assert _span_name(span) == "HTTP"

    def setup_status_400_is_error(self) -> None:
        self.response = _distant_call("http://weblog:7777/status?code=400")

    def test_status_400_is_error(self) -> None:
        _assert_status_error(_client_span(self.response), 400)

    def setup_status_500_is_error(self) -> None:
        self.response = _distant_call("http://weblog:7777/status?code=500")

    def test_status_500_is_error(self) -> None:
        _assert_status_error(_client_span(self.response), 500)

    def setup_status_3xx_not_error(self) -> None:
        self.response = _distant_call("http://weblog:7777/status?code=302")

    def test_status_3xx_not_error(self) -> None:
        _assert_status_not_error(_client_span(self.response), 302)

    def setup_url_full_credential_redaction(self) -> None:
        self.response = _distant_call("http://otel-user:otel-pass@weblog:7777/")

    def test_url_full_credential_redaction(self) -> None:
        full_url = str(_attributes(_client_span(self.response)).get("url.full", ""))
        assert "otel-user" not in full_url
        assert "otel-pass" not in full_url
        # Some HTTP APIs retain userinfo for the tracer to redact, while others remove it
        # while normalizing request options. If userinfo remains, both fields must be redacted.
        if "@" in full_url:
            assert "REDACTED:REDACTED@" in full_url

    def setup_url_full_query_obfuscation(self) -> None:
        self.response = _distant_call(f"http://weblog:7777/?token={_SENSITIVE_QUERY_VALUE}")

    def test_url_full_query_obfuscation(self) -> None:
        full_url = str(_attributes(_client_span(self.response)).get("url.full", ""))
        assert full_url.startswith("http://weblog:7777/?token=")
        assert _SENSITIVE_QUERY_VALUE not in full_url
        assert "redacted" in full_url.lower()


@rfc("https://docs.google.com/document/d/1SONUGEa38eLumE5b6gnNhykFhzZL9uQpsnMFq06uDMY/edit")
@features.semantic_core_validations
@scenarios.otel_semantics_otlp
class Test_OtelSemantics_OTLP:
    """OTLP export retains required attributes and their specified integer types."""

    def setup_status_code_is_integer_type(self) -> None:
        self.response = _distant_call()

    def test_status_code_is_integer_type(self) -> None:
        for span in (_server_span(self.response), _client_span(self.response)):
            status_code = _attributes(span).get("http.response.status_code")
            assert isinstance(status_code, int), (
                f"http.response.status_code must be an OTLP IntValue, got {type(status_code).__name__}"
            )

    def setup_server_port_is_integer_type(self) -> None:
        self.response = _distant_call()

    def test_server_port_is_integer_type(self) -> None:
        server_port = _attributes(_client_span(self.response)).get("server.port")
        assert isinstance(server_port, int), f"server.port must be an OTLP IntValue, got {type(server_port).__name__}"
        assert server_port == 7777

    def setup_otel_attributes_present_otlp(self) -> None:
        self.response = _distant_call()

    def test_otel_attributes_present_otlp(self) -> None:
        server_attrs = _attributes(_server_span(self.response))
        assert all(
            key in server_attrs
            for key in ("http.request.method", "url.path", "url.scheme", "http.response.status_code")
        )

        client_attrs = _attributes(_client_span(self.response))
        assert all(
            key in client_attrs
            for key in (
                "http.request.method",
                "url.full",
                "server.address",
                "server.port",
                "http.response.status_code",
            )
        )

    def setup_legacy_attributes_absent_otlp(self) -> None:
        self.response = _distant_call()

    def test_legacy_attributes_absent_otlp(self) -> None:
        server_attrs = _attributes(_server_span(self.response))
        for legacy in ("http.method", "http.url", "http.status_code", "http.useragent", "http.client_ip"):
            assert legacy not in server_attrs

        client_attrs = _attributes(_client_span(self.response))
        for legacy in ("http.method", "http.url", "out.host", "peer.hostname"):
            assert legacy not in client_attrs


@rfc("https://docs.google.com/document/d/1SONUGEa38eLumE5b6gnNhykFhzZL9uQpsnMFq06uDMY/edit")
@features.semantic_core_validations
@scenarios.otel_semantics_otlp_custom_error_statuses
class Test_OtelSemantics_OTLP_Spans_Http_ErrorStatusConfiguration:
    """User-configured error status ranges take precedence over OTel defaults."""

    def setup_server_error_statuses_config_overrides(self) -> None:
        self.response = weblog.get("/")

    def test_server_error_statuses_config_overrides(self) -> None:
        span = _server_span(self.response)
        assert _attributes(span).get("http.response.status_code") == 200
        assert _span_is_error(span), "configured HTTP server status 200 must be marked as an error"

    def setup_client_error_statuses_config_overrides(self) -> None:
        self.response = _distant_call()

    def test_client_error_statuses_config_overrides(self) -> None:
        span = _client_span(self.response)
        assert _attributes(span).get("http.response.status_code") == 200
        assert _span_is_error(span), "configured HTTP client status 200 must be marked as an error"
