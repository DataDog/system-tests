# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

"""Validate that HTTP spans honor the OpenTelemetry HTTP semantic conventions when
``DD_TRACE_OTEL_SEMANTICS_ENABLED=true`` (the OTEL_SEMANTICS scenario).

This is an opt-in, *mutually exclusive* behavior: when enabled, HTTP server and client
spans emit the OpenTelemetry attribute names *instead* of the Datadog ones (the Datadog
names are replaced, not added alongside). Span name and type are unaffected.

Spec: https://opentelemetry.io/docs/specs/semconv/http/http-spans/
"""

from utils import features, interfaces, scenarios, weblog
from utils.dd_types import DataDogLibrarySpan


_HTTP_METHODS = ("GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "TRACE", "PATCH")


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
            if "server.port" in meta:
                _ = int(meta["server.port"])  # must be an int when present
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
            if "network.peer.port" in meta:
                _ = int(meta["network.peer.port"])  # must be an int when present
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
            if "server.port" in meta:
                _ = int(meta["server.port"])
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
            if "network.peer.port" in meta:
                _ = int(meta["network.peer.port"])  # must be an int when present
            return True

        interfaces.library.validate_one_span(self.r, validator=validator, full_trace=True)
