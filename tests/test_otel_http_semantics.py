# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

"""OpenTelemetry HTTP semantic-convention system tests.

The behavior tests run over both supported transports:

* ``OTEL_SEMANTICS`` validates the tracer-to-Agent payload.
* ``OTEL_SEMANTICS_OTLP`` validates the direct OTLP export.
* ``OTEL_SEMANTICS_STATS`` validates that the span and the trace stats agree.
* ``OTEL_SEMANTICS_UPSTREAM_SDK`` runs the same behavior tests against an upstream
  OpenTelemetry SDK weblog rather than a Datadog tracer. That scenario is a measurement, not a
  gate: an assertion an upstream SDK fails is either a bug in the assertion or a place where
  this RFC deviates from upstream behavior, and either answer is worth having.

Transport-specific helpers below normalize those payloads so every semantic assertion is
identical on both paths. OTLP-only tests additionally validate attribute value types and
custom error-status configuration.

Two conventions in here are deliberate and load-bearing:

* Span-name expectations are derived from the attributes the span itself reports, never
  hardcoded to a literal, because the RFC excludes the server span's ``http.route`` value and
  name value from the cross-tracer contract as framework-specific.
* Attributes whose specified value type is an int go through ``_assert_int_attribute``, which
  asserts where the key lives and what type it has, because the two transports have different
  and incompatible obligations for the same attribute.

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

# Datadog keys that have an OTel equivalent and so must be replaced, not duplicated, under the
# flag. http.endpoint is deliberately not here: it has no OTel equivalent and is retained.
_LEGACY_SERVER_KEYS = (
    "http.method",
    "http.url",
    "http.status_code",
    "http.useragent",
    "http.client_ip",
    "http.hostname",
    "network.client.ip",
    "http.query.string",
)
_LEGACY_CLIENT_KEYS = (
    "http.method",
    "http.url",
    "http.status_code",
    "out.host",
    "peer.hostname",
    "network.destination.name",
)


def _is_otlp_scenario() -> bool:
    return context.scenario in (
        scenarios.otel_semantics_otlp,
        scenarios.otel_semantics_otlp_custom_error_statuses,
        scenarios.otel_semantics_upstream_sdk,
    )


def _attributes(span: HttpSpan) -> dict[str, Any]:
    """Every attribute on the span, regardless of transport.

    On the Datadog agent protocol ``meta`` and ``metrics`` are flattened together, so this view
    is only safe for presence and absence checks and for string-valued attributes. Anything
    whose specified value type is an int must go through ``_assert_int_attribute`` instead,
    because the flattened view cannot say which map the value came from.
    """
    if isinstance(span, DataDogLibrarySpan):
        return {**span.meta, **span.metrics}
    # The OTLP deserializer only flattens the attribute list into a dict when it is non-empty,
    # so an attribute-less span still carries the raw `[]`. Normalize it to a mapping.
    attributes = span.get("attributes")
    return attributes if isinstance(attributes, dict) else {}


def _assert_int_attribute(span: HttpSpan, key: str, expected: int) -> None:
    """Assert an int-typed OTel attribute is in the right place, as the right type.

    The RFC sets two different obligations for the same attribute:

    * OTLP export MUST carry the value with its specified type, so an int here.
    * DD MsgPack export (any protocol version) MUST carry every attribute as a string in
      ``meta``, even when the specified value type is not a string.

    A bare ``attributes[key] == 200`` cannot tell those apart. On the agent path it silently
    requires the value to be a number in ``metrics``, because ``"200" == 200`` is False while
    ``200.0 == 200`` is True. So assert the location and the type explicitly.
    """
    if _is_otlp_scenario():
        value = _attributes(span).get(key)
        assert value is not None, f"{key} is absent from the OTLP export"
        assert not isinstance(value, bool), f"{key} must be an OTLP intValue, got a boolValue ({value!r})"
        assert isinstance(value, int), (
            f"{key} must be exported as an OTLP intValue, got {type(value).__name__} ({value!r})"
        )
        assert value == expected, f"expected {key} == {expected}, got {value}"
        return

    assert isinstance(span, DataDogLibrarySpan), "the agent path must yield a Datadog library span"
    meta, metrics = span.meta, span.metrics

    assert not (key in meta and key in metrics), (
        f"{key} must not be present in both meta and metrics (meta={meta.get(key)!r}, metrics={metrics.get(key)!r})"
    )
    assert key in meta, (
        f"{key} must be a string in meta on the Datadog agent protocol, found metrics={metrics.get(key)!r}"
    )
    assert meta[key] == str(expected), f"expected meta[{key!r}] == {str(expected)!r}, got {meta[key]!r}"


def _expected_span_name(span: HttpSpan, target_key: str) -> str:
    """The span name derived from this span's own attributes.

    ``{method} {target}`` when the span publishes a target, else bare ``{method}``, where
    ``{method}`` is the value of ``http.request.method`` verbatim, including ``_OTHER``.

    This is the OpenTelemetry Collector's ``set_semconv_span_name`` algorithm
    (``processor/transformprocessor/internal/traces``), which Datadog agreed to adopt for OTel
    semantics mode rather than mirroring whatever each upstream instrumentation library happens
    to emit. Its ``httpSpanName`` reads ``http.request.method`` and one target key, ``http.route``
    for SERVER and ``url.template`` for CLIENT, and returns ``method + " " + target`` or bare
    ``method``. It performs no substitution, so an unknown method names the span ``_OTHER /users``
    and not ``HTTP /users``. The HTTP semconv prose says ``HTTP`` there; the collector does not,
    and the collector is the algorithm we agreed to follow.

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
    if isinstance(span, DataDogLibrarySpan):
        return str(span["resource"])
    return str(span["name"])


def _span_is_error(span: HttpSpan) -> bool:
    if isinstance(span, DataDogLibrarySpan):
        return int(span.get("error", 0) or 0) == 1

    status = span.get("status", {})
    return int(status.get("code", StatusCode.STATUS_CODE_UNSET.value)) == StatusCode.STATUS_CODE_ERROR.value


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
    if _is_otlp_scenario():
        request_id = request.get_rid()
        server_spans: list[dict[str, Any]] = []
        for span in _iter_otlp_spans(request):
            if span.get("kind") != SpanKind.SERVER.value:
                continue
            server_spans.append(span)
            # Correlation is plumbing, not an assertion, so accept whichever user-agent key the
            # tracer happens to emit. A tracer that has converted its client spans but not its
            # server spans still reports the request id under the legacy names, and insisting on
            # user_agent.original here silently picks an unrelated span and fails every client
            # test for a reason that has nothing to do with the client.
            attrs = _attributes(span)
            user_agent = " ".join(
                str(attrs.get(key, ""))
                for key in ("user_agent.original", "http.useragent", "http.request.headers.user-agent")
            )
            if request_id in user_agent:
                return span

        # No user-agent key carried the request id. Fall back only when the batch leaves no room
        # for ambiguity: with more than one server span, picking the first would silently assert
        # against another request's span, and an absence check would then pass for free.
        assert server_spans, "no SERVER span found in the OTLP payload"
        assert len(server_spans) == 1, (
            f"could not correlate a SERVER span to request {request_id} by user agent, and the OTLP "
            f"batch holds {len(server_spans)} server spans, so there is no unambiguous fallback"
        )
        return server_spans[0]

    spans = [span for _, _, span in interfaces.library.get_spans(request)]
    assert spans, "no server span found in the tracer payload"
    assert len(spans) == 1, f"expected one request-correlated server span, found {len(spans)}"
    return spans[0]


def _client_span(request: HttpResponse) -> HttpSpan:
    if _is_otlp_scenario():
        # An OTLP payload is a batch, so it holds spans from unrelated requests. Every distant
        # call in this file targets weblog:7777, so matching on the target alone can return
        # another test's client span. Pin to the trace of the request-correlated server span.
        trace_id = _server_span(request).get("traceId")
        assert trace_id, "the request-correlated server span carries no traceId"
        spans: Iterator[HttpSpan] = (s for s in _iter_otlp_spans(request) if s.get("traceId") == trace_id)
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
    _assert_int_attribute(span, "http.response.status_code", status_code)
    assert _span_is_error(span), f"HTTP {status_code} span must be marked as an error"
    assert _attributes(span).get("error.type") == str(status_code)


def _assert_status_not_error(span: HttpSpan, status_code: int) -> None:
    _assert_int_attribute(span, "http.response.status_code", status_code)
    assert not _span_is_error(span), f"HTTP {status_code} span must not be marked as an error"
    assert "error.type" not in _attributes(span)


@rfc("https://docs.google.com/document/d/1SONUGEa38eLumE5b6gnNhykFhzZL9uQpsnMFq06uDMY/edit")
@features.semantic_core_validations
@scenarios.otel_semantics
@scenarios.otel_semantics_otlp
@scenarios.otel_semantics_upstream_sdk
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

    def setup_legacy_attributes_absent(self) -> None:
        self.response = weblog.get("/", headers={"X-Forwarded-For": _CLIENT_ADDRESS})

    def test_legacy_attributes_absent(self) -> None:
        span = _server_span(self.response)
        attrs = _attributes(span)
        for legacy in _LEGACY_SERVER_KEYS:
            assert legacy not in attrs, f"legacy Datadog key {legacy!r} must be absent under the flag"

        if isinstance(span, DataDogLibrarySpan):
            # The flattened view hides a stale numeric copy in metrics, and http.status_code is
            # the key the agent's stats aggregation reads, so check both maps explicitly.
            for legacy in _LEGACY_SERVER_KEYS:
                assert legacy not in span.metrics, f"legacy Datadog key {legacy!r} must be absent from metrics"

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
        _assert_name_has_no_uri_path(span)

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
        """``_OTHER`` substitutes the method token only, so a resolved route still appends.

        The name comes from the collector algorithm (see ``_expected_span_name``), which uses the
        value of ``http.request.method`` verbatim. An unmatched verb is therefore ``_OTHER`` in
        the name, not the literal ``HTTP`` the HTTP semconv prose asks for. Two consequences the
        assertions below encode: the whole name does not collapse to one token, so a framework
        that resolves a route still gets ``_OTHER {route}``, and the raw verb never survives into
        the name, which is what catches a tracer that does not normalize at all.
        """
        span = _server_span(self.response)
        attrs = _attributes(span)
        assert attrs.get("http.request.method") == "_OTHER"
        assert attrs.get("http.request.method_original") == "PROPFIND"
        assert _span_name(span) == _expected_span_name(span, "http.route")
        assert "PROPFIND" not in _span_name(span), "the raw method must never appear in the span name"
        _assert_name_has_no_uri_path(span)

    def setup_span_name_route_invariance(self) -> None:
        self.response_low = weblog.get("/sample_rate_route/1")
        self.response_high = weblog.get("/sample_rate_route/99999")

    def test_span_name_route_invariance(self) -> None:
        """``http.route`` and the span name are invariant across path-parameter values.

        ``route != "/sample_rate_route/1"`` is satisfiable while still leaking the parameter,
        for example ``/sample_rate_route/1x``. The property that actually matters for
        cardinality is that two different parameter values collapse onto one route and one name.
        """
        low, high = _server_span(self.response_low), _server_span(self.response_high)
        route_low = _attributes(low).get("http.route")
        route_high = _attributes(high).get("http.route")

        assert route_low, "the server span must publish http.route for a parameterized route"
        assert route_low == route_high, (
            f"http.route must be invariant across parameter values: {route_low!r} vs {route_high!r}"
        )
        assert _span_name(low) == _span_name(high), (
            f"span name must be invariant across parameter values: {_span_name(low)!r} vs {_span_name(high)!r}"
        )
        assert "99999" not in str(route_high), f"the path parameter leaked into http.route {route_high!r}"
        assert "99999" not in _span_name(high), f"the path parameter leaked into the span name {_span_name(high)!r}"

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

    def setup_server_port(self) -> None:
        self.response = weblog.get("/")

    def test_server_port(self) -> None:
        """``server.port`` is Conditionally Required on server spans and its value type is int.

        The RFC's own test tables only check ``server.port`` on client spans, but the server
        attribute table requires it too, and it is subject to the same two-transport typing rule
        as the status code.
        """
        span = _server_span(self.response)
        assert _attributes(span).get("server.address"), "server.port is required once server.address is set"
        _assert_int_attribute(span, "server.port", 7777)

    def setup_http_endpoint_retained(self) -> None:
        # http.endpoint is the endpoint-aggregation fallback for requests the framework
        # resolved no route for, so a routed path never carries it in any tracer. Ask for a
        # path with no route, with DD_TRACE_RESOURCE_RENAMING_ENABLED set by the scenario.
        self.response = weblog.get("/no_such_route_xyz")

    def test_http_endpoint_retained(self) -> None:
        """``http.endpoint`` is Datadog-only with no OTel equivalent, so it is retained.

        Retained on both transports, including OTLP, because ASM and endpoint aggregation read
        it. A tracer that drops it under the flag is doing the opposite of the RFC guidance.
        """
        span = _server_span(self.response)
        assert _attributes(span).get("http.endpoint"), (
            "http.endpoint must be retained under the flag, on the agent path and on OTLP"
        )

    def setup_span_kind_is_server(self) -> None:
        self.response = weblog.get("/")

    def test_span_kind_is_server(self) -> None:
        """The span kind MUST be SERVER.

        Worth its own assertion because every other selector in this module filters on the kind
        and silently finds nothing when it is wrong, which reads as a pass rather than a failure.
        """
        span = _server_span(self.response)
        if isinstance(span, DataDogLibrarySpan):
            assert span.meta.get("span.kind") == "server", f"got span.kind {span.meta.get('span.kind')!r}"
        else:
            assert span.get("kind") == SpanKind.SERVER.value, f"got OTLP kind {span.get('kind')!r}"

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
@scenarios.otel_semantics_upstream_sdk
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

    def setup_legacy_attributes_absent(self) -> None:
        self.response = _distant_call()

    def test_legacy_attributes_absent(self) -> None:
        span = _client_span(self.response)
        attrs = _attributes(span)
        for legacy in _LEGACY_CLIENT_KEYS:
            assert legacy not in attrs, f"legacy Datadog key {legacy!r} must be absent under the flag"

        if isinstance(span, DataDogLibrarySpan):
            for legacy in _LEGACY_CLIENT_KEYS:
                assert legacy not in span.metrics, f"legacy Datadog key {legacy!r} must be absent from metrics"

    def setup_url_path_absent_on_client(self) -> None:
        self.response = _distant_call("http://weblog:7777/sample_rate_route/1?otel=visible")

    def test_url_path_absent_on_client(self) -> None:
        """The client attribute table specifies ``url.full`` only, not the ``url.*`` split.

        A negative assertion, because nothing else in the suite stops a tracer from emitting
        ``url.path`` and ``url.query`` on a client span alongside ``url.full``.
        """
        attrs = _attributes(_client_span(self.response))
        assert attrs.get("url.full"), "url.full is Required on client spans"
        for key in ("url.path", "url.scheme", "url.query"):
            assert key not in attrs, f"{key!r} is a server-span attribute and must not appear on a client span"

    def setup_span_name_is_method(self) -> None:
        self.response = _distant_call()

    def test_span_name_is_method(self) -> None:
        """Bare ``{method}`` on client spans, because no Datadog tracer emits ``url.template``.

        Derived rather than hardcoded so the test stays correct if ``url.template`` ever lands.
        ``url.template`` is the only target key the collector algorithm reads on a CLIENT span, so
        a tracer that appends the path or the host here is naming the span from something the
        algorithm never looks at. The ``HTTP `` prefix negative is the one that earns its keep:
        upstream otelhttp names client spans ``HTTP GET``, which is neither the method nor
        ``{method} {url.template}``.
        """
        span = _client_span(self.response)
        name = _span_name(span)
        assert name == _expected_span_name(span, "url.template")
        assert not name.startswith("HTTP "), (
            f"the client span name must be {{method}} or {{method}} {{url.template}}, got {name!r}"
        )

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
        if isinstance(span, DataDogLibrarySpan):
            assert span.meta.get("span.kind") == "client", f"got span.kind {span.meta.get('span.kind')!r}"
        else:
            assert span.get("kind") == SpanKind.CLIENT.value, f"got OTLP kind {span.get('kind')!r}"

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
@scenarios.otel_semantics_otlp
@scenarios.otel_semantics_upstream_sdk
class Test_OtelSemantics_OTLP_Server:
    """OTLP export of the HTTP **server** span: required attributes, and the two integer types.

    Split from the client class on purpose. A tracer converts one span kind at a time, so a test
    that asserts on the server span and the client span together reports a tracer that has finished
    half the work as having finished none of it, and gives whoever is doing the other half no signal
    at all.

    ``server.port`` and ``http.response.status_code`` are the only two attributes the RFC types as
    ``int``; everything else in its tables is a string, so those are the only two typed here.
    """

    def setup_status_code_is_integer_type(self) -> None:
        self.response = weblog.get("/")

    def test_status_code_is_integer_type(self) -> None:
        span = _server_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 200)
        assert not isinstance(_attributes(span)["http.response.status_code"], float), (
            "http.response.status_code must be an OTLP intValue, not a doubleValue"
        )

    def setup_server_port_is_integer_type(self) -> None:
        self.response = weblog.get("/")

    def test_server_port_is_integer_type(self) -> None:
        _assert_int_attribute(_server_span(self.response), "server.port", 7777)

    def setup_http_endpoint_retained_otlp(self) -> None:
        self.response = weblog.get("/no_such_route_xyz")

    def test_http_endpoint_retained_otlp(self) -> None:
        """``http.endpoint`` survives the OTLP export as a Datadog-only attribute.

        The RFC keeps it explicitly on OTLP spans, so an OTLP-side filter that strips Datadog-only
        meta keys must not take it with it.
        """
        assert _attributes(_server_span(self.response)).get("http.endpoint"), (
            "http.endpoint must be retained on OTLP spans"
        )

    def setup_otel_attributes_present_otlp(self) -> None:
        self.response = weblog.get("/")

    def test_otel_attributes_present_otlp(self) -> None:
        attrs = _attributes(_server_span(self.response))
        for key in ("http.request.method", "url.path", "url.scheme", "http.response.status_code"):
            assert key in attrs, f"{key} must be present on the OTLP server span"

    def setup_legacy_attributes_absent_otlp(self) -> None:
        self.response = weblog.get("/")

    def test_legacy_attributes_absent_otlp(self) -> None:
        attrs = _attributes(_server_span(self.response))
        for legacy in _LEGACY_SERVER_KEYS:
            assert legacy not in attrs, f"legacy Datadog key {legacy!r} must be absent under the flag"


@rfc("https://docs.google.com/document/d/1SONUGEa38eLumE5b6gnNhykFhzZL9uQpsnMFq06uDMY/edit")
@features.semantic_core_validations
@scenarios.otel_semantics_otlp
@scenarios.otel_semantics_upstream_sdk
class Test_OtelSemantics_OTLP_Client:
    """OTLP export of the HTTP **client** span. See ``Test_OtelSemantics_OTLP_Server`` on the split."""

    def setup_status_code_is_integer_type(self) -> None:
        self.response = _distant_call()

    def test_status_code_is_integer_type(self) -> None:
        span = _client_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 200)
        assert not isinstance(_attributes(span)["http.response.status_code"], float), (
            "http.response.status_code must be an OTLP intValue, not a doubleValue"
        )

    def setup_server_port_is_integer_type(self) -> None:
        self.response = _distant_call()

    def test_server_port_is_integer_type(self) -> None:
        _assert_int_attribute(_client_span(self.response), "server.port", 7777)

    def setup_otel_attributes_present_otlp(self) -> None:
        self.response = _distant_call()

    def test_otel_attributes_present_otlp(self) -> None:
        attrs = _attributes(_client_span(self.response))
        for key in (
            "http.request.method",
            "url.full",
            "server.address",
            "server.port",
            "http.response.status_code",
        ):
            assert key in attrs, f"{key} must be present on the OTLP client span"

    def setup_legacy_attributes_absent_otlp(self) -> None:
        self.response = _distant_call()

    def test_legacy_attributes_absent_otlp(self) -> None:
        attrs = _attributes(_client_span(self.response))
        for legacy in _LEGACY_CLIENT_KEYS:
            assert legacy not in attrs, f"legacy Datadog key {legacy!r} must be absent under the flag"


@rfc("https://docs.google.com/document/d/1SONUGEa38eLumE5b6gnNhykFhzZL9uQpsnMFq06uDMY/edit")
@features.semantic_core_validations
@scenarios.otel_semantics_otlp_custom_error_statuses
class Test_OtelSemantics_OTLP_Spans_Http_ErrorStatusConfiguration:
    """User-configured error status ranges take precedence over OTel defaults."""

    def setup_server_error_statuses_config_overrides(self) -> None:
        self.response = weblog.get("/")

    def test_server_error_statuses_config_overrides(self) -> None:
        span = _server_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 200)
        assert _span_is_error(span), "configured HTTP server status 200 must be marked as an error"
        assert _attributes(span).get("error.type") == "200", (
            "error.type must be the status code as a string whenever the status made the span an error"
        )

    def setup_client_error_statuses_config_overrides(self) -> None:
        self.response = _distant_call()

    def test_client_error_statuses_config_overrides(self) -> None:
        span = _client_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 200)
        assert _span_is_error(span), "configured HTTP client status 200 must be marked as an error"
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

    def setup_client_error_statuses_config_excludes_500(self) -> None:
        self.response = _distant_call("http://weblog:7777/status?code=500")

    def test_client_error_statuses_config_excludes_500(self) -> None:
        """As above for client spans, where the OTel default range is the wider 400-599."""
        span = _client_span(self.response)
        _assert_int_attribute(span, "http.response.status_code", 500)
        assert not _span_is_error(span), (
            "HTTP 500 is outside the configured client error range, so the span must not be an error"
        )
        assert "error.type" not in _attributes(span)


@rfc("https://docs.google.com/document/d/1SONUGEa38eLumE5b6gnNhykFhzZL9uQpsnMFq06uDMY/edit")
@features.semantic_core_validations
@scenarios.otel_semantics_stats
class Test_OtelSemantics_Stats_Consistency:
    """The span's error decision and the trace-stats error decision agree under the flag.

    Renaming attributes at export time keeps in-process consumers working, but it also means the
    span and the stats can be computed from two different rules. An export-time transform that
    flips ``error=1`` for a client 5xx while stats still apply the Datadog rule produces a trace
    that is an error and a stats bucket that is not. Nothing at span level can detect that.

    The status dimension is the second half: ``http.status_code`` is the key the agent's
    aggregation reads today, and the flag suppresses it, so the numeric status has to reach stats
    some other way or ``HTTPStatusCode`` silently becomes 0.
    """

    ERROR_STATUS = 500
    REQUEST_COUNT = 3

    def setup_stats_agree_with_span_error(self) -> None:
        for _ in range(self.REQUEST_COUNT):
            self.response = weblog.get("/status", params={"code": str(self.ERROR_STATUS)})
        interfaces.library.wait_for_client_side_stats_payload()

    def test_stats_agree_with_span_error(self) -> None:
        span = _server_span(self.response)
        resource = _span_name(span)
        assert _span_is_error(span), f"HTTP {self.ERROR_STATUS} server span must be an error"

        buckets = [
            bucket
            for bucket in interfaces.agent.get_stats(resource=resource)
            if bucket.get("HTTPStatusCode") == self.ERROR_STATUS
        ]
        assert buckets, (
            f"no stats bucket for resource {resource!r} with HTTPStatusCode {self.ERROR_STATUS}. Either the "
            f"resource name the tracer reports to stats differs from the span name, or the status dimension "
            f"was lost when the legacy http.status_code key was suppressed"
        )

        hits = sum(bucket["Hits"] for bucket in buckets)
        errors = sum(bucket["Errors"] for bucket in buckets)
        assert hits == errors, (
            f"the span is an error but stats recorded {errors} errors out of {hits} hits for {resource!r}, "
            f"so the span and the stats disagree"
        )

    def setup_stats_agree_with_span_success(self) -> None:
        for _ in range(self.REQUEST_COUNT):
            self.response = weblog.get("/status", params={"code": "200"})
        interfaces.library.wait_for_client_side_stats_payload()

    def test_stats_agree_with_span_success(self) -> None:
        span = _server_span(self.response)
        resource = _span_name(span)
        assert not _span_is_error(span), "HTTP 200 server span must not be an error"

        buckets = [
            bucket for bucket in interfaces.agent.get_stats(resource=resource) if bucket.get("HTTPStatusCode") == 200
        ]
        assert buckets, f"no stats bucket for resource {resource!r} with HTTPStatusCode 200"
        assert sum(bucket["Errors"] for bucket in buckets) == 0, (
            f"the span is not an error but stats recorded errors for {resource!r}"
        )
