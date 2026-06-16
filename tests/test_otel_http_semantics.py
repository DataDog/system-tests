# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

"""Validate that HTTP spans honor the OpenTelemetry HTTP semantic conventions when
``DD_TRACE_OTEL_SEMANTICS_ENABLED=true`` (the OTEL_SEMANTICS scenario).

This is an opt-in, *mutually exclusive* behavior: when enabled, HTTP server and client
spans emit the OpenTelemetry attribute names *instead* of the Datadog ones (the Datadog
names are replaced, not added alongside). Span type is unaffected.

Spec: https://opentelemetry.io/docs/specs/semconv/http/http-spans/
"""

from utils import features, interfaces, scenarios, weblog
from utils.dd_types import DataDogLibrarySpan


_HTTP_METHODS = ("GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "TRACE", "PATCH")


def _numeric_tag(span: DataDogLibrarySpan, key: str):
    """Return a numeric OTel attribute regardless of where the tracer stored it.

    dd-trace-js routes numeric tags (``server.port``, ``network.peer.port``) into ``metrics``
    as numbers, while dd-trace-java/dotnet keep them in ``meta`` as strings. Look in both.
    """
    if key in span["meta"]:
        return span["meta"][key]
    metrics = span["metrics"]
    return metrics.get(key) if metrics else None


@features.semantic_core_validations
@scenarios.otel_semantics
class Test_HttpServerOtelSemantics:
    """HTTP server spans emit OpenTelemetry semantic-convention attribute names.

    The spec assigns each attribute a requirement level. ``http.request.method`` /
    ``url.path`` / ``url.scheme`` are Required (asserted present). ``server.address`` and
    ``user_agent.original`` are Recommended and ``http.response.status_code`` is
    Conditionally Required; they are asserted present here because a real system-tests
    request always carries a Host + User-Agent header and always receives a response (and
    request->span correlation itself relies on the user agent being captured).
    """

    def setup_request_method(self):
        self.r = weblog.get("/")

    def test_request_method(self):
        """``http.method`` becomes ``http.request.method``."""

        def validator(span: DataDogLibrarySpan):
            if span.get("parent_id") not in (0, None):  # server span is the root span
                return None
            if span.get("type") != "web":  # only http server spans
                return None

            meta = span["meta"]
            assert "http.request.method" in meta, "server span expects an http.request.method tag"
            assert meta["http.request.method"] in _HTTP_METHODS, (
                f"unexpected http.request.method '{meta['http.request.method']}'"
            )
            assert "http.method" not in meta, "legacy http.method tag must be absent in OTel mode"
            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_response_status_code(self):
        self.r = weblog.get("/")

    def test_response_status_code(self):
        """``http.status_code`` becomes ``http.response.status_code``."""

        def validator(span: DataDogLibrarySpan):
            if span.get("parent_id") not in (0, None):
                return None
            if span.get("type") != "web":
                return None

            meta = span["meta"]
            assert "http.response.status_code" in meta, "server span expects an http.response.status_code tag"
            _ = int(meta["http.response.status_code"])  # must be an int
            assert "http.status_code" not in meta, "legacy http.status_code tag must be absent in OTel mode"
            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_url(self):
        self.r = weblog.get("/")

    def test_url(self):
        """``http.url`` is decomposed into ``url.path`` + ``url.scheme`` for server spans."""

        def validator(span: DataDogLibrarySpan):
            if span.get("parent_id") not in (0, None):
                return None
            if span.get("type") != "web":
                return None

            meta = span["meta"]
            assert "url.path" in meta, "server span expects a url.path tag"
            assert "url.scheme" in meta, "server span expects a url.scheme tag"
            assert meta["url.scheme"] in ("http", "https"), f"unexpected url.scheme '{meta['url.scheme']}'"
            assert "http.url" not in meta, "legacy http.url tag must be absent in OTel mode"
            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_server_address(self):
        self.r = weblog.get("/")

    def test_server_address(self):
        """The request host becomes ``server.address`` (and ``server.port`` when known)."""

        def validator(span: DataDogLibrarySpan):
            if span.get("parent_id") not in (0, None):
                return None
            if span.get("type") != "web":
                return None

            meta = span["meta"]
            assert "server.address" in meta, "server span expects a server.address tag"
            assert meta["server.address"], "server.address must not be empty"
            port = _numeric_tag(span, "server.port")
            if port is not None:
                _ = int(port)  # parseable as int when present (meta string or metrics number)
            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_user_agent(self):
        self.r = weblog.get("/")

    def test_user_agent(self):
        """``http.useragent`` becomes ``user_agent.original``."""

        def validator(span: DataDogLibrarySpan):
            if span.get("parent_id") not in (0, None):
                return None
            if span.get("type") != "web":
                return None

            meta = span["meta"]
            assert "user_agent.original" in meta, "server span expects a user_agent.original tag"
            assert "http.useragent" not in meta, "legacy http.useragent tag must be absent in OTel mode"
            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_url_query(self):
        self.r = weblog.get("/", params={"ddtest": "1"})

    def test_url_query(self):
        """``http.query.string`` becomes ``url.query`` (present only when a query string is sent)."""

        def validator(span: DataDogLibrarySpan):
            if span.get("parent_id") not in (0, None):
                return None
            if span.get("type") != "web":
                return None

            meta = span["meta"]
            assert "url.query" in meta, "server span expects a url.query tag when a query string is sent"
            assert meta["url.query"], "url.query must not be empty"
            assert "http.query.string" not in meta, "legacy http.query.string tag must be absent in OTel mode"
            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_error_type(self):
        self.r = weblog.get("/status?code=500")

    def test_error_type(self):
        """On a 5xx response the server span carries ``error.type`` set to the status code string.

        Per the spec, 4xx is not a server error, so error.type is only expected for 5xx.
        """

        def validator(span: DataDogLibrarySpan):
            if span.get("parent_id") not in (0, None):
                return None
            if span.get("type") != "web":
                return None

            meta = span["meta"]
            assert meta.get("http.response.status_code") == "500", "expected http.response.status_code=500"
            assert meta.get("error.type") == "500", "5xx server span expects error.type set to the status code string"
            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_client_ip_attributes(self):
        self.r = weblog.get("/")

    def test_client_ip_attributes(self):
        """``http.client_ip`` -> ``client.address`` and ``network.client.ip`` -> ``network.peer.address``.

        Both are Recommended-level (and depend on client-IP resolution), so they are validated
        only when present rather than required.
        """

        def validator(span: DataDogLibrarySpan):
            if span.get("parent_id") not in (0, None):
                return None
            if span.get("type") != "web":
                return None

            meta = span["meta"]
            if "client.address" in meta:
                assert meta["client.address"], "client.address must not be empty when present"
            if "network.peer.address" in meta:
                assert meta["network.peer.address"], "network.peer.address must not be empty when present"
            peer_port = _numeric_tag(span, "network.peer.port")
            if peer_port is not None:
                _ = int(peer_port)  # parseable as int when present (meta string or metrics number)
            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_http_route(self):
        self.r = weblog.get("/sample_rate_route/1")

    def test_http_route(self):
        """``http.route`` is the low-cardinality route template, not the concrete URL path.

        ``http.route`` is unchanged by the OTel feature (same name in both conventions); the spec
        requires it be a low-cardinality target and that instrumentation never use the URI path.
        """

        def validator(span: DataDogLibrarySpan):
            if span.get("parent_id") not in (0, None):
                return None
            if span.get("type") != "web":
                return None

            meta = span["meta"]
            assert "http.route" in meta, "server span expects an http.route tag on a routed endpoint"
            route = meta["http.route"]
            assert "sample_rate_route" in route, f"unexpected http.route '{route}'"
            # must be the template, not the concrete path the client requested
            assert route != "/sample_rate_route/1", (
                f"http.route must be the low-cardinality template, not the raw path: '{route}'"
            )
            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_resource_name(self):
        self.r = weblog.get("/sample_rate_route/1")

    def test_resource_name(self):
        """The span resource is the low-cardinality ``{method} {http.route}``, never the raw URL path.

        OTel's span-name rule maps onto the Datadog resource. dd-trace-java rewrites the resource to
        this form; dd-trace-dotnet and dd-trace-js leave the already-compliant DD resource unchanged.
        The expected value is derived from the same span's http.route so per-tracer template syntax
        (``{i}`` vs ``{i:int}`` vs ``:i``) cancels out. The no-route and unknown-method (``_OTHER``)
        cases diverge between tracers and are intentionally not exercised here.
        """

        def validator(span: DataDogLibrarySpan):
            if span.get("parent_id") not in (0, None):  # entry/root span only
                return None
            # the java spring.handler child is also type=="web" but is not the entry span; the
            # parent_id gate above excludes it so we read the servlet.request resource.
            if span.get("type") != "web":
                return None

            route = span["meta"].get("http.route")
            assert route, "entry web span expects an http.route tag on a routed endpoint"
            assert route != "/sample_rate_route/1", f"http.route must be the template, not the raw path: '{route}'"

            resource = span["resource"]  # top-level field, not meta and not span["name"]
            assert resource == f"GET {route}", (
                f"resource '{resource}' must be the low-cardinality 'GET {{route}}' (got route '{route}')"
            )
            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_no_route_resource(self):
        self.r = weblog.get("/no_such_route_xyz")

    def test_no_route_resource(self):
        """With no matched route the resource is the bare ``{method}`` — never the URL path.

        Spec: the span name is ``{method}`` when no low-cardinality target is available, and
        instrumentation MUST NOT use the URI path as the target.
        """

        def validator(span: DataDogLibrarySpan):
            if span.get("parent_id") not in (0, None):
                return None
            if span.get("type") != "web":
                return None

            method = span["meta"]["http.request.method"]
            resource = span["resource"]
            assert resource == method, f"no-route resource must be the bare method '{method}', not '{resource}'"
            assert "no_such_route_xyz" not in resource, "resource must not contain the URI path"
            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_request_method_normalization(self):
        self.r = weblog.request("BOGUS", "/")

    def test_request_method_normalization(self):
        """An unknown HTTP method normalizes to ``_OTHER``, with the raw value in
        ``http.request.method_original``.
        """

        def validator(span: DataDogLibrarySpan):
            if span.get("parent_id") not in (0, None):
                return None
            if span.get("type") != "web":
                return None

            meta = span["meta"]
            assert meta.get("http.request.method") == "_OTHER", (
                f"unknown method must normalize to _OTHER, got '{meta.get('http.request.method')}'"
            )
            assert meta.get("http.request.method_original") == "BOGUS", (
                "http.request.method_original must hold the raw method"
            )
            return True

        interfaces.library.validate_one_span(self.r, validator=validator)

    def setup_other_method_span_name(self):
        self.r = weblog.request("BOGUS", "/no_such_route_xyz")

    def test_other_method_span_name(self):
        """For an unknown method with no matched route, the resource's method component MUST be ``HTTP``.

        Spec: ``{method}`` is ``HTTP`` when ``http.request.method`` is ``_OTHER``. No tracer
        implements this for the Datadog resource yet (java keeps the raw method; dotnet/js keep the
        raw method, dotnet also retains the path), so it is currently gated for every implementation.
        """

        def validator(span: DataDogLibrarySpan):
            if span.get("parent_id") not in (0, None):
                return None
            if span.get("type") != "web":
                return None

            resource = span["resource"]
            assert resource == "HTTP", f"_OTHER span resource must be \"HTTP\" (no route matched), got '{resource}'"
            return True

        interfaces.library.validate_one_span(self.r, validator=validator)


@features.semantic_core_validations
@scenarios.otel_semantics
class Test_HttpClientOtelSemantics:
    """HTTP client spans emit OpenTelemetry semantic-convention attribute names.

    Per the OTel HTTP spec, client spans carry ``url.full`` (not the decomposed
    ``url.path`` / ``url.query`` used for server spans); ``url.scheme`` is allowed but
    opt-in, so it is not asserted here.
    """

    def _client_span(self, span: DataDogLibrarySpan) -> bool:
        # the outbound HTTP call is the only span.kind=client span in the trace
        return span.get("meta", {}).get("span.kind") == "client"

    def setup_request_method(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/"})

    def test_request_method(self):
        """``http.method`` becomes ``http.request.method`` on the client span."""

        def validator(span: DataDogLibrarySpan):
            if not self._client_span(span):
                return None

            meta = span["meta"]
            assert "http.request.method" in meta, "client span expects an http.request.method tag"
            assert meta["http.request.method"] in _HTTP_METHODS, (
                f"unexpected http.request.method '{meta['http.request.method']}'"
            )
            assert "http.method" not in meta, "legacy http.method tag must be absent in OTel mode"
            return True

        interfaces.library.validate_one_span(self.r, validator=validator, full_trace=True)

    def setup_response_status_code(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/"})

    def test_response_status_code(self):
        """``http.status_code`` becomes ``http.response.status_code`` on the client span."""

        def validator(span: DataDogLibrarySpan):
            if not self._client_span(span):
                return None

            meta = span["meta"]
            assert "http.response.status_code" in meta, "client span expects an http.response.status_code tag"
            _ = int(meta["http.response.status_code"])
            assert "http.status_code" not in meta, "legacy http.status_code tag must be absent in OTel mode"
            return True

        interfaces.library.validate_one_span(self.r, validator=validator, full_trace=True)

    def setup_url_full(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/"})

    def test_url_full(self):
        """Client spans use ``url.full``; the server-only ``url.path`` / ``url.query`` are absent."""

        def validator(span: DataDogLibrarySpan):
            if not self._client_span(span):
                return None

            meta = span["meta"]
            assert "url.full" in meta, "client span expects a url.full tag"
            assert meta["url.full"], "url.full must not be empty"
            assert "url.path" not in meta, "url.path must not be set on client spans"
            assert "url.query" not in meta, "url.query must not be set on client spans"
            assert "http.url" not in meta, "legacy http.url tag must be absent in OTel mode"
            return True

        interfaces.library.validate_one_span(self.r, validator=validator, full_trace=True)

    def setup_server_address(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/"})

    def test_server_address(self):
        """The destination host/port become ``server.address`` / ``server.port`` (was out.host / out.port)."""

        def validator(span: DataDogLibrarySpan):
            if not self._client_span(span):
                return None

            meta = span["meta"]
            assert "server.address" in meta, "client span expects a server.address tag"
            assert meta["server.address"], "server.address must not be empty"
            # server.port is Required for client spans per the spec; the distant-call URL uses a
            # non-default port so every compliant tracer must emit it.
            port = _numeric_tag(span, "server.port")
            assert port is not None, "client span expects a server.port tag (Required for client spans)"
            _ = int(port)
            for legacy in ("out.host", "out.port"):
                assert legacy not in meta, f"legacy {legacy} tag must be absent in OTel mode"
            return True

        interfaces.library.validate_one_span(self.r, validator=validator, full_trace=True)

    def setup_error_type(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/status?code=500"})

    def test_error_type(self):
        """On a 4xx/5xx response, the client span carries ``error.type`` set to the status code string."""

        def validator(span: DataDogLibrarySpan):
            if not self._client_span(span):
                return None
            meta = span["meta"]
            if meta.get("http.response.status_code") != "500":  # the client span that hit the erroring endpoint
                return None
            assert meta.get("error.type") == "500", "client span on a 5xx expects error.type set to the status code"
            return True

        interfaces.library.validate_one_span(self.r, validator=validator, full_trace=True)

    def setup_network_peer_attributes(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/"})

    def test_network_peer_attributes(self):
        """``network.peer.address`` / ``network.peer.port`` are Recommended; validated only when present."""

        def validator(span: DataDogLibrarySpan):
            if not self._client_span(span):
                return None
            meta = span["meta"]
            if "network.peer.address" in meta:
                assert meta["network.peer.address"], "network.peer.address must not be empty when present"
            peer_port = _numeric_tag(span, "network.peer.port")
            if peer_port is not None:
                _ = int(peer_port)  # parseable as int when present (meta string or metrics number)
            return True

        interfaces.library.validate_one_span(self.r, validator=validator, full_trace=True)
