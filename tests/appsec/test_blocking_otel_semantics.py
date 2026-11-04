# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

"""AppSec path-parameter blocking with OTel HTTP semantics enabled.

With DD_TRACE_OTEL_SEMANTICS_ENABLED the tracer exports traces over OTLP, so the library interface
receives nothing: spans are read from the open_telemetry interface instead. WAF trigger events are
stored in meta_struct, which is not asserted here; these tests rely on response codes and plain
span attributes.
"""

from collections.abc import Iterator
from typing import Any

from utils import features, interfaces, rfc, scenarios, weblog
from utils._weblog import HttpResponse
from utils.dd_constants import SpanKind


type OtlpSpan = dict[str, Any]

_CUSTOM_EVENT_TAG = "appsec.events.system_tests_appsec_event.value"


def _attributes(span: OtlpSpan) -> dict[str, Any]:
    # The OTLP deserializer leaves an empty attribute list as [] instead of a mapping.
    attributes = span.get("attributes")
    return attributes if isinstance(attributes, dict) else {}


def _span_kind(span: OtlpSpan) -> int:
    kind = span.get("kind", SpanKind.UNSPECIFIED.value)
    if isinstance(kind, str) and not kind.isdigit():
        return SpanKind[kind.removeprefix("SPAN_KIND_")].value
    return int(kind)


def _request_spans(request: HttpResponse) -> Iterator[OtlpSpan]:
    """Spans correlated to the request by user agent, plus all their descendants."""
    for _, _, span in interfaces.open_telemetry.get_otel_spans(request):
        yield span


def _server_span(request: HttpResponse) -> OtlpSpan:
    spans = [span for span in _request_spans(request) if _span_kind(span) == SpanKind.SERVER.value]
    assert len(spans) == 1, f"expected one SERVER span for request {request.get_rid()}, got {len(spans)}"
    return spans[0]


def _application_span_names(request: HttpResponse) -> list[str]:
    """Return Django middleware and view span names from the request trace."""
    names = (str(span.get("name", "")) for span in _request_spans(request))
    return sorted(name for name in names if ".middleware." in name or name == "app.urls.waf")


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2667021177/Suspicious+requests+blocking")
@features.appsec_request_blocking
@scenarios.appsec_blocking_otel_semantics
class Test_Blocking_request_path_params_OtelSemantics:
    """Blocking on server.request.path_params happens before application code runs under OTel semantics"""

    def setup_blocking(self) -> None:
        self.block_params = weblog.get("/params/AiKfOeRcvG45")
        self.block_waf = weblog.get("/waf/AiKfOeRcvG45")

    def test_blocking(self) -> None:
        for response in (self.block_params, self.block_waf):
            assert response.status_code == 403

    def setup_non_blocking(self) -> None:
        # Query parameters are not path parameters.
        self.non_blocked = weblog.get("/waf/noharm?value=AiKfOeRcvG45")

    def test_non_blocking(self) -> None:
        assert self.non_blocked.status_code == 200

    def setup_blocking_before(self) -> None:
        self.tagged = weblog.get("/tag_value/clean_value_3878/200")
        self.blocked = weblog.get("/tag_value/tainted_value_AiKfOeRcvG45/200")

    def test_blocking_before(self) -> None:
        assert self.tagged.status_code == 200
        assert self.tagged.text == "Value tagged"
        assert _attributes(_server_span(self.tagged)).get(_CUSTOM_EVENT_TAG) == "clean_value_3878"

        assert self.blocked.status_code == 403
        assert _CUSTOM_EVENT_TAG not in _attributes(_server_span(self.blocked))

    def setup_blocked_request_skips_middleware_and_view(self) -> None:
        self.clean_before_middleware = weblog.get("/tag_value/clean_value_3878/200")
        self.blocked_before_middleware = weblog.get("/tag_value/tainted_value_AiKfOeRcvG45/200")

    def test_blocked_request_skips_middleware_and_view(self) -> None:
        """No middleware or view span may exist on a request blocked on its path parameters"""
        assert self.clean_before_middleware.status_code == 200
        clean_names = _application_span_names(self.clean_before_middleware)
        assert any(".middleware." in name for name in clean_names), "no middleware spans on clean request"
        assert "app.urls.waf" in clean_names, "no view span on clean request"

        assert self.blocked_before_middleware.status_code == 403
        spans = list(_request_spans(self.blocked_before_middleware))
        assert spans, "no OTLP spans correlated to the blocked request"
        ran = _application_span_names(self.blocked_before_middleware)
        assert not ran, f"application code ran before the request was blocked: {ran}"
