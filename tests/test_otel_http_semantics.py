# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

"""OpenTelemetry HTTP semantic-convention system tests over direct OTLP export.

Several conventions in here are deliberate and load-bearing:

* Span-name expectations are derived from the attributes the span itself reports, never
  hardcoded to a literal, because the RFC excludes the server span's ``http.route`` value and
  name value from the cross-tracer contract as framework-specific.
* Attributes whose specified value type is an int go through ``_assert_int_attribute``, which
  verifies that OTLP preserved their primitive type.
* This suite tests the RFC's Datadog OTel-semantics profile, not generic conformance with every
  valid implementation of the upstream HTTP semantic conventions. The profile intentionally
  narrows or overrides upstream behavior to keep tracer output consistent and preserve existing
  Datadog features:

  * Upstream span-name formats are SHOULD requirements; the RFC makes them MUST requirements so
    every tracer emits the same low-cardinality resource names and sampling rules see those names
    before export.
  * Upstream classifies client 4xx and all 5xx responses as errors with SHOULD requirements. The
    RFC fixes those classifications as the default cross-tracer behavior. It also chooses the
    status-code string for ``error.type`` even though upstream permits an exception type or a
    component-specific identifier.
  * ``DD_TRACE_HTTP_SERVER_ERROR_STATUSES`` and ``DD_TRACE_HTTP_CLIENT_ERROR_STATUSES`` take
    precedence over the OTel defaults. A configured 200 range therefore marks 200 as an error and
    excludes otherwise-default statuses such as 500 when they are outside the configured range.
  * Upstream marks ``user_agent.original``, ``client.address``, ``network.peer.address``, and
    server-side ``server.address`` as Recommended. The RFC requires their presence in these tests
    to replace existing Datadog attributes consistently and preserve their APM consumers.
  * Query strings use existing Datadog obfuscation, including keys such as ``token``. Adopting
    OTel's exact default sensitive-key list and ``REDACTED`` behavior is explicitly deferred by
    the RFC.
  * Datadog attributes with OTel equivalents are replaced, peer-service default derivation is
    disabled, and Datadog-only attributes such as ``http.endpoint`` remain. This makes exported
    data the RFC's intended superset of OTel rather than a pure upstream payload.

Specification: https://opentelemetry.io/docs/specs/semconv/http/http-spans/
RFC: https://docs.google.com/document/d/1SONUGEa38eLumE5b6gnNhykFhzZL9uQpsnMFq06uDMY/edit
"""

from collections.abc import Iterator
from typing import Any

from utils import features, interfaces, rfc, scenarios, weblog
from utils._weblog import HttpResponse
from utils.dd_constants import SpanKind, StatusCode


type HttpSpan = dict[str, Any]

_DISTANT_CALL_TARGET = "http://weblog:7777/"
_SENSITIVE_QUERY_VALUE = "otel-sensitive-value"
_CLIENT_ADDRESS = "203.0.113.42"

# Datadog keys that have an OTel equivalent and so must be replaced, not duplicated, under the
# flag. http.endpoint is deliberately not here: it has no OTel equivalent and is retained.
_DATADOG_SERVER_KEYS = (
    "http.method",
    "http.url",
    "http.status_code",
    "http.useragent",
    "http.client_ip",
    "http.hostname",
    "network.client.ip",
    "http.query.string",
)
_DATADOG_CLIENT_KEYS = (
    "http.method",
    "http.url",
    "http.status_code",
    "out.host",
    "peer.hostname",
    "network.destination.name",
)


def _attributes(span: HttpSpan) -> dict[str, Any]:
    """Return the flattened attributes of an OTLP span."""
    # The OTLP deserializer only flattens the attribute list into a dict when it is non-empty,
    # so an attribute-less span still carries the raw `[]`. Normalize it to a mapping.
    attributes = span.get("attributes")
    return attributes if isinstance(attributes, dict) else {}


def _assert_int_attribute(span: HttpSpan, key: str, expected: int) -> None:
    """Assert that an OTLP attribute retained its required integer type."""
    value = _attributes(span).get(key)
    assert type(value) is int, f"{key} must be an OTLP intValue, got {type(value).__name__} ({value!r})"
    assert value == expected, f"expected {key} == {expected}, got {value}"


def _expected_span_name(span: HttpSpan, target_key: str) -> str:
    """The span name derived from this span's own attributes.

    ``{method} {target}`` when the span publishes a target, else bare ``{method}``, where
    ``{method}`` is the value of ``http.request.method`` verbatim or ``HTTP`` when ``http.request.method`` is ``_OTHER``.

    This is the OpenTelemetry Collector's ``set_semconv_span_name`` algorithm
    (``processor/transformprocessor/internal/traces``), which Datadog agreed to adopt for OTel
    semantics mode rather than mirroring whatever each upstream instrumentation library happens
    to emit. Its ``httpSpanName`` reads ``http.request.method`` and one target key, ``http.route``
    for SERVER and ``url.template`` for CLIENT, and returns ``method + " " + target`` or bare
    ``method``. The one notable deviation is that an unknown method (``_OTHER``) names the span ``HTTP /users``
    and not ``_OTHER /users``, which aligns with the HTTP semconv spec.

    Deriving instead of hardcoding is deliberate: the RFC's system-tests section excludes the
    server span's ``http.route`` value and the server span's name value from the cross-tracer
    contract because both are framework-specific. A hardcoded ``"GET /users"`` contradicts that.
    Deriving keeps the assertion framework-neutral, makes per-framework template syntax
    (``{i}`` / ``{i:int}`` / ``<i>`` / ``:i``) cancel out, and still catches the two real bugs:
    falling back to the URI path as a target, and substituting the whole name rather than only
    the method token when the method is not an accepted one.
    """
    attrs = _attributes(span)
    method = attrs.get("http.request.method")
    assert method, "span carries no http.request.method, so no span name can be derived"
    method = "HTTP" if method == "_OTHER" else method
    target = attrs.get(target_key)
    return f"{method} {target}" if target else str(method)


def _assert_name_has_no_uri_path(span: HttpSpan) -> None:
    """Instrumentation MUST NOT default to using the URI path as a target."""
    name = _span_name(span)
    attrs = _attributes(span)
    path = str(attrs.get("url.path") or "")
    route = str(attrs.get("http.route") or "")

    if path and path not in ("/", route):
        assert path not in name, f"span name {name!r} must not contain the URI path {path!r}"


def _span_name(span: HttpSpan) -> str:
    return str(span["name"])


def _protobuf_enum_value(value: object, names: dict[str, int], *, field: str) -> int:
    """Normalize protobuf enums represented as numbers, numeric strings, or symbolic names."""
    if isinstance(value, bool):
        raise TypeError(f"{field} must be a protobuf enum value, got bool {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            if value in names:
                return names[value]
    raise TypeError(f"unsupported {field} protobuf enum value {value!r}")


def _span_kind(span: HttpSpan) -> int:
    return _protobuf_enum_value(
        span.get("kind", SpanKind.UNSPECIFIED.value),
        {f"SPAN_KIND_{kind.name}": kind.value for kind in SpanKind},
        field="span.kind",
    )


def _status_code(value: object) -> int:
    return _protobuf_enum_value(
        value,
        {
            name: status.value
            for status in StatusCode
            for name in (status.name, status.name.removeprefix("STATUS_CODE_"))
        },
        field="status.code",
    )


def _metric_span_kind(value: object) -> int:
    return _protobuf_enum_value(
        value,
        {name: kind.value for kind in SpanKind for name in (f"SPAN_KIND_{kind.name}", kind.name, kind.name.lower())},
        field="metric span.kind",
    )


def _span_is_error(span: HttpSpan) -> bool:
    status = span.get("status", {})
    return _status_code(status.get("code", StatusCode.STATUS_CODE_UNSET.value)) == StatusCode.STATUS_CODE_ERROR.value


def _span_is_sampled(span: HttpSpan) -> bool:
    return bool(int(span.get("flags", 0)) & 1)


def _iter_otlp_spans(request: HttpResponse) -> Iterator[dict[str, Any]]:
    """Yield every span in the OTLP payloads associated with ``request``, each one once.

    ``get_otel_spans`` yields one ``(data, content, span)`` triple per correlated span, so the
    same payload comes back once per span it holds. Dedupe on the span id rather than stopping
    after the first payload: a tracer that flushes the server span and the client span in two
    separate exports would otherwise lose the second one.
    """
    seen: set[str] = set()
    for _, content, _ in interfaces.open_telemetry.get_otel_spans(request):
        for resource_span in content.get("resourceSpans", []):
            for scope_span in resource_span.get("scopeSpans", []):
                for span in scope_span.get("spans", []):
                    span_id = str(span.get("spanId", ""))
                    if span_id in seen:
                        continue
                    seen.add(span_id)
                    yield span


def _server_span(request: HttpResponse) -> HttpSpan:
    request_id = request.get_rid()
    server_span_count = 0
    matched_spans: list[HttpSpan] = []
    for span in _iter_otlp_spans(request):
        if _span_kind(span) != SpanKind.SERVER.value:
            continue
        server_span_count += 1
        user_agent = " ".join(
            str(_attributes(span).get(key, ""))
            for key in ("user_agent.original", "http.useragent", "http.request.headers.user-agent")
        )
        if request_id in user_agent:
            matched_spans.append(span)

    assert matched_spans, (
        f"could not correlate a SERVER span to request {request_id} by user agent; "
        f"the correlated OTLP payloads contained {server_span_count} SERVER spans"
    )
    assert len(matched_spans) == 1, (
        f"expected exactly one SERVER span correlated to request {request_id}, found {len(matched_spans)}"
    )
    return matched_spans[0]


def _client_span(request: HttpResponse) -> HttpSpan:
    # An OTLP payload is a batch, so it holds spans from unrelated requests. Every distant
    # call in this file targets weblog:7777, so matching on the target alone can return
    # another test's client span. Pin to the trace of the request-correlated server span.
    trace_id = _server_span(request).get("traceId")
    assert trace_id, "the request-correlated server span carries no traceId"
    spans: Iterator[HttpSpan] = (s for s in _iter_otlp_spans(request) if s.get("traceId") == trace_id)

    for span in spans:
        attrs = _attributes(span)
        if _span_kind(span) == SpanKind.CLIENT.value and (
            attrs.get("server.address") == "weblog" or "weblog:7777" in str(attrs.get("url.full", ""))
        ):
            return span

    raise AssertionError("no HTTP CLIENT span to weblog:7777 found")


def _distant_call(target: str = _DISTANT_CALL_TARGET, *, method: str = "GET") -> HttpResponse:
    return weblog.get("/make_distant_call", params={"url": target, "method": method})


def _otlp_attribute_value(attribute: dict[str, Any]) -> object:
    value = attribute.get("value", {})
    for value_type in (
        "stringValue",
        "boolValue",
        "intValue",
        "doubleValue",
        "arrayValue",
        "kvlistValue",
        "bytesValue",
    ):
        if value_type in value:
            result = value[value_type]
            return int(result) if value_type == "intValue" else result
    raise AssertionError(f"unsupported OTLP attribute value {value!r}")


def _metric_attributes(data_point: dict[str, Any]) -> dict[str, object]:
    return {str(attribute["key"]): _otlp_attribute_value(attribute) for attribute in data_point.get("attributes", [])}


def _trace_metric_data_points() -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for data in interfaces.open_telemetry.get_data(path_filters="/v1/metrics"):
        content = data.get("request", {}).get("content", {})
        for resource_metric in content.get("resourceMetrics", []):
            for scope_metric in resource_metric.get("scopeMetrics", []):
                for metric in scope_metric.get("metrics", []):
                    if metric.get("name") == "traces.span.sdk.metrics.duration":
                        points.extend(metric.get("histogram", {}).get("dataPoints", []))
    return points


def _trace_metric(span: HttpSpan, expected_kind: SpanKind) -> dict[str, Any]:
    """Return the metric matching the span's name, HTTP status, and kind."""
    span_name = _span_name(span)
    status_code = _attributes(span).get("http.response.status_code")
    assert status_code is not None, "the HTTP span must carry http.response.status_code"
    for data_point in _trace_metric_data_points():
        attrs = _metric_attributes(data_point)
        if (
            attrs.get("span.name") == span_name
            and attrs.get("http.response.status_code") == status_code
            and attrs.get("span.kind") is not None
            and _metric_span_kind(attrs.get("span.kind")) == expected_kind.value
        ):
            return data_point
    raise AssertionError(
        f"no HTTP trace metric found for span.name={span_name!r}, "
        f"http.response.status_code={status_code!r}, and span.kind={expected_kind.name}"
    )


def _client_trace_metric(span: HttpSpan) -> dict[str, Any]:
    return _trace_metric(span, SpanKind.CLIENT)


def _server_trace_metric(span: HttpSpan) -> dict[str, Any]:
    return _trace_metric(span, SpanKind.SERVER)


@rfc("https://docs.google.com/document/d/1SONUGEa38eLumE5b6gnNhykFhzZL9uQpsnMFq06uDMY/edit")
@features.semantic_core_validations
@scenarios.otel_semantics_otlp
class Test_OtelSemantics_Spans_Http_Server:
    """HTTP server spans use OTel names, values, naming, and status semantics."""

    def setup_otel_attributes_present(self) -> None:
        self.response = weblog.get("/")

    def test_otel_attributes_present(self) -> None:
        span = _server_span(self.response)
        attrs = _attributes(span)
        assert attrs.get("http.request.method") == "GET"
        assert attrs.get("url.path") == "/"
        assert attrs.get("url.scheme") in ("http", "https")
        _assert_int_attribute(span, "http.response.status_code", 200)

    def setup_datadog_attributes_absent(self) -> None:
        self.response = weblog.get("/", headers={"X-Forwarded-For": _CLIENT_ADDRESS})

    def test_datadog_attributes_absent(self) -> None:
        attrs = _attributes(_server_span(self.response))
        for datadog_key in _DATADOG_SERVER_KEYS:
            assert datadog_key not in attrs, f"Datadog key {datadog_key!r} must be absent under the flag"

    def setup_span_name_with_route(self) -> None:
        self.response = weblog.get("/sample_rate_route/1")

    def test_span_name_with_route(self) -> None:
        """Name is ``{method} {http.route}``, derived from the route this span reports.

        The RFC's system-tests section excludes the server span's ``http.route`` value and the
        server span's name value from the cross-tracer contract because they are
        framework-specific, so the expectation is derived from the span rather than hardcoded
        to a literal such as ``GET /users``.
        """
        span = _server_span(self.response)
        route = _attributes(span).get("http.route")
        assert route, "http.route must be published when the framework resolved a route"
        assert route != "/sample_rate_route/1", "http.route must be a low-cardinality route template"
        assert _span_name(span) == _expected_span_name(span, "http.route")

    def setup_span_name_route_invariance(self) -> None:
        self.first_response = weblog.get("/sample_rate_route/1")
        self.second_response = weblog.get("/sample_rate_route/2")

    def test_span_name_route_invariance(self) -> None:
        """Resolved routes and route-derived names remain stable across path parameters."""
        first_span = _server_span(self.first_response)
        second_span = _server_span(self.second_response)
        first_attrs = _attributes(first_span)
        second_attrs = _attributes(second_span)
        first_route = first_attrs.get("http.route")
        second_route = second_attrs.get("http.route")
        assert first_attrs.get("url.path") == "/sample_rate_route/1"
        assert second_attrs.get("url.path") == "/sample_rate_route/2"
        assert first_route, "the first request must report a resolved http.route"
        assert second_route, "the second request must report a resolved http.route"
        assert first_route == second_route, "http.route must not vary with path-parameter values"
        assert _span_name(first_span) == _span_name(second_span), (
            "a route-derived span name must not vary with path-parameter values"
        )

    def setup_span_name_without_route(self) -> None:
        self.response = weblog.get("/no_such_route_xyz")

    def test_span_name_without_route(self) -> None:
        """Bare ``{method}`` when no route resolved, and never the URI path.

        Conditioned on the route the span itself reports rather than assuming a 404 means no
        route: frameworks with a catch-all (Spring resolves ``/**``, a Go mux resolves ``/``)
        publish a real low-cardinality route for an unmatched path, and ``{method} {route}`` is
        the correct name there. Hardcoding ``"GET"`` tests the weblog's route table, not the
        tracer. The URI-path negative below is what actually guards the MUST NOT.
        """
        span = _server_span(self.response)
        assert _span_name(span) == _expected_span_name(span, "http.route")
        assert "no_such_route_xyz" not in _span_name(span)
        _assert_name_has_no_uri_path(span)

    def setup_span_name_unknown_method(self) -> None:
        # Node's HTTP parser rejects arbitrary tokens before instrumentation can see them.
        # PROPFIND is accepted on the wire but is outside the RFC 9110 + PATCH + QUERY allowlist.
        self.response = weblog.request("PROPFIND", "/")

    def test_span_name_unknown_method(self) -> None:
        """``HTTP`` substitutes for ``_OTHER`` in the name, while a resolved route still appends.

        The attribute is normalized to ``_OTHER`` and preserves the original method separately.
        The HTTP semantic conventions require the span-name method token to become ``HTTP``.
        """
        span = _server_span(self.response)
        attrs = _attributes(span)
        assert attrs.get("http.request.method") == "_OTHER"
        assert attrs.get("http.request.method_original") == "PROPFIND"
        assert _span_name(span) == _expected_span_name(span, "http.route")
        assert "PROPFIND" not in _span_name(span), "the raw method must never appear in the span name"
        _assert_name_has_no_uri_path(span)

    def setup_status_500_no_exception_is_status_code_error(self) -> None:
        self.response = weblog.get("/status", params={"code": "500"})

    def test_status_500_no_exception_is_status_code_error(self) -> None:
        span = _server_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 500)
        assert _span_is_error(span), "HTTP 500 span must be marked as an error"
        assert _attributes(span).get("error.type") == "500"

    def setup_status_400_is_not_error(self) -> None:
        self.response = weblog.get("/status", params={"code": "400"})

    def test_status_400_is_not_error(self) -> None:
        span = _server_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 400)
        assert not _span_is_error(span), "HTTP 400 span must not be marked as an error"
        assert "error.type" not in _attributes(span)

    def setup_status_3xx_is_not_error(self) -> None:
        self.response = weblog.get("/status", params={"code": "302"}, allow_redirects=False)

    def test_status_3xx_is_not_error(self) -> None:
        span = _server_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 302)
        assert not _span_is_error(span), "HTTP 302 span must not be marked as an error"
        assert "error.type" not in _attributes(span)

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

    def setup_server_port(self) -> None:
        self.response = weblog.get("/")

    def test_server_port(self) -> None:
        span = _server_span(self.response)
        assert _attributes(span).get("server.address"), "server.port is required once server.address is set"
        _assert_int_attribute(span, "server.port", 7777)

    def setup_http_endpoint_retained(self) -> None:
        # http.endpoint is the endpoint-aggregation fallback for requests the framework
        # resolved no route for, so use an unmatched path.
        self.response = weblog.get("/no_such_route_xyz")

    def test_http_endpoint_retained(self) -> None:
        """``http.endpoint`` is Datadog-only with no OTel equivalent, so it is retained."""
        span = _server_span(self.response)
        assert _attributes(span).get("http.endpoint"), "http.endpoint must be retained on the OTLP span"

    def setup_span_kind_is_server(self) -> None:
        self.response = weblog.get("/")

    def test_span_kind_is_server(self) -> None:
        """The span kind MUST be SERVER.

        Worth its own assertion because every other selector in this module filters on the kind
        and silently finds nothing when it is wrong, which reads as a pass rather than a failure.
        """
        span = _server_span(self.response)
        assert _span_kind(span) == SpanKind.SERVER.value, f"got OTLP kind {span.get('kind')!r}"


@rfc("https://docs.google.com/document/d/1SONUGEa38eLumE5b6gnNhykFhzZL9uQpsnMFq06uDMY/edit")
@features.semantic_core_validations
@scenarios.otel_semantics_otlp
class Test_OtelSemantics_Spans_Http_Client:
    """HTTP client spans use OTel names, values, naming, and status semantics."""

    def setup_otel_attributes_present(self) -> None:
        self.response = _distant_call()

    def test_otel_attributes_present(self) -> None:
        span = _client_span(self.response)
        attrs = _attributes(span)
        assert attrs.get("http.request.method") == "GET"
        assert attrs.get("url.full") == _DISTANT_CALL_TARGET
        assert attrs.get("server.address") == "weblog"
        _assert_int_attribute(span, "server.port", 7777)
        _assert_int_attribute(span, "http.response.status_code", 200)

    def setup_datadog_attributes_absent(self) -> None:
        self.response = _distant_call()

    def test_datadog_attributes_absent(self) -> None:
        attrs = _attributes(_client_span(self.response))
        for datadog_key in _DATADOG_CLIENT_KEYS:
            assert datadog_key not in attrs, f"Datadog key {datadog_key!r} must be absent under the flag"

    def setup_peer_service_suppressed(self) -> None:
        self.response = _distant_call()

    def test_peer_service_suppressed(self) -> None:
        """OTel semantics forces peer-service defaults off despite ``DD_TRACE_PEER_SERVICE_DEFAULTS_ENABLED=true``."""
        attrs = _attributes(_client_span(self.response))
        assert "peer.service" not in attrs
        assert "_dd.peer.service.source" not in attrs

    def setup_span_name_is_method(self) -> None:
        self.response = _distant_call()

    def test_span_name_is_method(self) -> None:
        """Bare ``{method}`` on client spans, because no Datadog tracer emits ``url.template``.

        Derived rather than hardcoded so the test stays correct if ``url.template`` ever lands.
        ``url.template`` is the only target key the collector algorithm reads on a CLIENT span, so
        a tracer that appends the path or the host here is naming the span from something the
        algorithm never looks at.
        """
        span = _client_span(self.response)
        assert _span_name(span) == _expected_span_name(span, "url.template")

    def setup_span_name_unknown_method(self) -> None:
        self.response = _distant_call(method="PROPFIND")

    def test_span_name_unknown_method(self) -> None:
        span = _client_span(self.response)
        attrs = _attributes(span)
        assert attrs.get("http.request.method") == "_OTHER"
        assert attrs.get("http.request.method_original") == "PROPFIND"
        assert _span_name(span) == _expected_span_name(span, "url.template")
        assert "PROPFIND" not in _span_name(span), "the raw method must never appear in the span name"

    def setup_span_kind_is_client(self) -> None:
        self.response = _distant_call()

    def test_span_kind_is_client(self) -> None:
        """The span kind MUST be CLIENT."""
        span = _client_span(self.response)
        assert _span_kind(span) == SpanKind.CLIENT.value, f"got OTLP kind {span.get('kind')!r}"

    def setup_status_400_is_error(self) -> None:
        self.response = _distant_call("http://weblog:7777/status?code=400")

    def test_status_400_is_error(self) -> None:
        span = _client_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 400)
        assert _span_is_error(span), "HTTP 400 span must be marked as an error"
        assert _attributes(span).get("error.type") == "400"

    def setup_status_500_is_error(self) -> None:
        self.response = _distant_call("http://weblog:7777/status?code=500")

    def test_status_500_is_error(self) -> None:
        span = _client_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 500)
        assert _span_is_error(span), "HTTP 500 span must be marked as an error"
        assert _attributes(span).get("error.type") == "500"
        assert not span.get("status", {}).get("message"), (
            "HTTP status errors must have an empty status description when the status code explains the error"
        )

    def setup_status_3xx_not_error(self) -> None:
        self.response = _distant_call("http://weblog:7777/status?code=302")

    def test_status_3xx_not_error(self) -> None:
        span = _client_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 302)
        assert not _span_is_error(span), "HTTP 302 span must not be marked as an error"
        assert "error.type" not in _attributes(span)

    def setup_url_full_credential_redaction(self) -> None:
        self.response = _distant_call("http://otel-user:otel-pass@weblog:7777/")

    def test_url_full_credential_redaction(self) -> None:
        full_url = str(_attributes(_client_span(self.response)).get("url.full", ""))
        # Without this the whole test passes for free on a tracer that never emits url.full.
        assert full_url, "url.full must be present on the client span for redaction to be checked"
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
@scenarios.otel_semantics_otlp_custom_error_statuses
class Test_OtelSemantics_OTLP_Spans_Http_ErrorStatusConfiguration:
    """User-configured server and client error ranges take precedence over OTel defaults."""

    def setup_server_error_statuses_config_overrides(self) -> None:
        self.response = weblog.get("/")

    def test_server_error_statuses_config_overrides(self) -> None:
        span = _server_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 200)
        assert _span_is_error(span), "configured HTTP server status 200 must be marked as an error"
        assert _attributes(span).get("error.type") == "200", (
            "error.type must be the status code as a string whenever the status made the span an error"
        )

    def setup_server_error_statuses_config_excludes_500(self) -> None:
        self.response = weblog.get("/status", params={"code": "500"})

    def test_server_error_statuses_config_excludes_500(self) -> None:
        """The configured range replaces the OTel rule, it does not add to it.

        The other half of precedence, and the half that was untested. With the range configured
        to 200 only, a 500 is outside it, so a tracer that hardcodes the 5xx threshold and merely
        unions the configured range still passes the positive test above and fails this one.
        """
        span = _server_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 500)
        assert not _span_is_error(span), (
            "HTTP 500 is outside the configured server error range, so the span must not be an error"
        )
        assert "error.type" not in _attributes(span)

    def setup_client_error_statuses_config_overrides(self) -> None:
        self.response = _distant_call()

    def test_client_error_statuses_config_overrides(self) -> None:
        span = _client_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 200)
        assert _span_is_error(span), "configured HTTP client status 200 must be marked as an error"
        assert _attributes(span).get("error.type") == "200"

    def setup_client_error_statuses_config_excludes_500(self) -> None:
        self.response = _distant_call("http://weblog:7777/status?code=500")

    def test_client_error_statuses_config_excludes_500(self) -> None:
        span = _client_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 500)
        assert not _span_is_error(span), (
            "HTTP 500 is outside the configured client error range, so the span must not be an error"
        )
        assert "error.type" not in _attributes(span)


@rfc("https://docs.google.com/document/d/1SONUGEa38eLumE5b6gnNhykFhzZL9uQpsnMFq06uDMY/edit")
@features.semantic_core_validations
@scenarios.otel_semantics_otlp_trace_metrics
class Test_OtelSemantics_OTLP_TraceMetrics:
    """OTLP trace metrics use the same early HTTP semantics and error decision as their spans."""

    def setup_trace_metric_agrees_with_client_error(self) -> None:
        self.response = _distant_call("http://weblog:7777/status?code=418")

    def test_trace_metric_agrees_with_client_error(self) -> None:
        span = _client_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 418)
        assert _span_is_error(span), "HTTP 418 client span must be an error"
        attrs = _metric_attributes(_client_trace_metric(span))
        assert attrs.get("http.request.method") == "GET"
        assert attrs.get("http.response.status_code") == 418
        assert _status_code(attrs.get("status.code")) == StatusCode.STATUS_CODE_ERROR.value

    def setup_trace_metric_agrees_with_client_success(self) -> None:
        self.response = _distant_call("http://weblog:7777/status?code=201")

    def test_trace_metric_agrees_with_client_success(self) -> None:
        span = _client_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 201)
        assert not _span_is_error(span), "HTTP 201 client span must not be an error"
        attrs = _metric_attributes(_client_trace_metric(span))
        assert attrs.get("http.request.method") == "GET"
        assert attrs.get("http.response.status_code") == 201
        assert "status.code" not in attrs, "successful HTTP trace metrics must leave OTel status unset"

    def setup_trace_metric_agrees_with_server_error(self) -> None:
        self.response = weblog.get("/status?code=503")

    def test_trace_metric_agrees_with_server_error(self) -> None:
        span = _server_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 503)
        assert _span_is_error(span), "HTTP 503 server span must be an error"
        attrs = _metric_attributes(_server_trace_metric(span))
        assert attrs.get("http.request.method") == "GET"
        assert attrs.get("http.response.status_code") == 503
        assert _status_code(attrs.get("status.code")) == StatusCode.STATUS_CODE_ERROR.value

    def setup_trace_metric_agrees_with_server_success(self) -> None:
        self.response = weblog.get("/status?code=202")

    def test_trace_metric_agrees_with_server_success(self) -> None:
        span = _server_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 202)
        assert not _span_is_error(span), "HTTP 202 server span must not be an error"
        attrs = _metric_attributes(_server_trace_metric(span))
        assert attrs.get("http.request.method") == "GET"
        assert attrs.get("http.response.status_code") == 202
        assert "status.code" not in attrs, "successful HTTP trace metrics must leave OTel status unset"


@rfc("https://docs.google.com/document/d/1SONUGEa38eLumE5b6gnNhykFhzZL9uQpsnMFq06uDMY/edit")
@features.semantic_core_validations
@scenarios.otel_semantics_otlp_sampling_rules
class Test_OtelSemantics_SamplingRules:
    """Sampling rules consume the OTel span name before the trace is exported."""

    def setup_otel_span_name_is_available_to_sampling_rules(self) -> None:
        self.matched_response = weblog.request("PROPFIND", "/")

    def test_otel_span_name_is_available_to_sampling_rules(self) -> None:
        matched_span = _server_span(self.matched_response)
        assert _attributes(matched_span).get("_dd.rule_psr") == 1, (
            "the HTTP* rule must be the sampling rule that kept the normalized unknown-method span"
        )
        trace_id = matched_span.get("traceId")
        assert trace_id, "the request-correlated matched span carries no traceId"
        matched_trace = [span for span in _iter_otlp_spans(self.matched_response) if span.get("traceId") == trace_id]
        assert matched_trace, "the matched trace must contain at least one exported span"
        assert all(_span_is_sampled(span) for span in matched_trace), (
            "every span in the trace kept by the HTTP* resource rule must carry the sampled flag"
        )

    def setup_server_span_name_is_available_before_client_sampling(self) -> None:
        self.distant_call_response = _distant_call()

    def test_server_span_name_is_available_before_client_sampling(self) -> None:
        server_span = _server_span(self.distant_call_response)
        client_span = _client_span(self.distant_call_response)

        assert server_span["traceId"] == client_span["traceId"]
        assert _attributes(server_span).get("_dd.rule_psr") == 1, (
            "the GET* rule must keep the server trace whether or not the route was resolved before client sampling"
        )
        assert _span_is_sampled(server_span)
        assert _span_is_sampled(client_span), "sampling the server trace must keep its outbound HTTP client span"
