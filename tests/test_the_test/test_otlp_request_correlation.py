from typing import Any
from unittest.mock import Mock, patch

import pytest

from tests.otel.test_tracing_otlp import OtelSpanRecord, _server_span_by_request_id
from utils import features, scenarios
from utils._weblog import HttpResponse
from utils.dd_constants import SpanKind
from utils.interfaces._open_telemetry import OpenTelemetryInterfaceValidator


REQUEST_ID = "A" * 36
USER_AGENT = f"system_tests rid/{REQUEST_ID}"
OTHER_USER_AGENT = "system_tests rid/" + "B" * 36
TEST_TAG = "system_tests.request.user_agent"
STANDARD_TAGS = ("http.request.headers.user-agent", "http.useragent", "user_agent.original")


def _payload(spans: list[dict[str, Any]]) -> dict[str, Any]:
    return {"request": {"content": {"resourceSpans": [{"scopeSpans": [{"spans": spans}]}]}}}


@features.not_reported
@scenarios.test_the_test
@pytest.mark.parametrize(
    ("attributes", "request_id", "matches"),
    [
        *[({key: USER_AGENT}, REQUEST_ID, True) for key in STANDARD_TAGS],
        ({TEST_TAG: USER_AGENT}, REQUEST_ID, True),
        ({TEST_TAG: OTHER_USER_AGENT}, REQUEST_ID, False),
        ({TEST_TAG: "without a request id"}, REQUEST_ID, False),
        ({}, REQUEST_ID, False),
        ({TEST_TAG: USER_AGENT}, "", False),
        *[({key: OTHER_USER_AGENT, TEST_TAG: USER_AGENT}, REQUEST_ID, False) for key in STANDARD_TAGS],
        *[({key: USER_AGENT, TEST_TAG: OTHER_USER_AGENT}, REQUEST_ID, True) for key in STANDARD_TAGS],
        ({"http.useragent": OTHER_USER_AGENT, "user_agent.original": USER_AGENT}, REQUEST_ID, True),
        ({"http.useragent": "", TEST_TAG: USER_AGENT}, REQUEST_ID, True),
        ({"http.useragent": None, TEST_TAG: USER_AGENT}, REQUEST_ID, True),
        ({TEST_TAG: 123}, REQUEST_ID, False),
        *[({key: 123, TEST_TAG: USER_AGENT}, REQUEST_ID, False) for key in STANDARD_TAGS],
        ([], REQUEST_ID, False),
        (None, REQUEST_ID, False),
    ],
)
@pytest.mark.parametrize("trace_id_key", ["traceId", "trace_id"])
def test_otlp_request_correlation(
    attributes: dict[str, Any] | list[dict[str, Any]] | None,
    request_id: str,
    *,
    matches: bool,
    trace_id_key: str,
) -> None:
    span = {"attributes": attributes, "kind": SpanKind.SERVER.value, "spanId": "root", trace_id_key: "trace"}
    payload = _payload([span])
    request = Mock(spec=HttpResponse)
    request.get_rid.return_value = request_id
    interface = OpenTelemetryInterfaceValidator()
    record = (payload["request"], payload["request"]["content"], span)

    with patch.object(interface, "get_data", return_value=[payload]) as get_data:
        assert list(interface.get_otel_trace_id(request)) == (["trace"] if matches else [])
        assert list(interface.get_otel_spans(request)) == ([record] if matches else [])
        get_data.assert_called_with(path_filters=["/api/v0.2/traces", "/v1/traces"])

    if matches:
        assert _server_span_by_request_id([record], request_id) == record
    else:
        with pytest.raises(AssertionError, match="found 0"):
            _server_span_by_request_id([record], request_id)


@features.not_reported
@scenarios.test_the_test
def test_otlp_correlates_descendants_exported_before_parent() -> None:
    root = {"spanId": "root", "attributes": {TEST_TAG: USER_AGENT}, "kind": SpanKind.SERVER.value}
    child = {"spanId": "child", "parentSpanId": "root", "kind": SpanKind.CLIENT.value, "attributes": []}
    grandchild = {"spanId": "grandchild", "parentSpanId": "child", "kind": SpanKind.SERVER.value}
    unrelated = {"spanId": "unrelated", "attributes": {TEST_TAG: OTHER_USER_AGENT}, "kind": SpanKind.SERVER.value}
    payloads = [_payload([grandchild, unrelated]), _payload([child]), _payload([root])]
    request = Mock(spec=HttpResponse)
    request.get_rid.return_value = REQUEST_ID
    interface = OpenTelemetryInterfaceValidator()

    with patch.object(interface, "get_data", return_value=payloads):
        records = list(interface.get_otel_spans(request))

    assert [record[2] for record in records] == [grandchild, child, root]
    assert _server_span_by_request_id(records, REQUEST_ID)[2] == root


@features.not_reported
@scenarios.test_the_test
def test_otlp_requires_exactly_one_matching_server_span() -> None:
    server = {"attributes": {TEST_TAG: USER_AGENT}, "kind": SpanKind.SERVER.value}
    client = {"attributes": {TEST_TAG: USER_AGENT}, "kind": SpanKind.CLIENT.value}
    server_record: OtelSpanRecord = ({}, {}, server)
    client_record: OtelSpanRecord = ({}, {}, client)
    assert _server_span_by_request_id([client_record, server_record], REQUEST_ID) == server_record
    with pytest.raises(AssertionError, match="found 0"):
        _server_span_by_request_id([client_record], REQUEST_ID)
    with pytest.raises(AssertionError, match="found 2"):
        _server_span_by_request_id([server_record, server_record], REQUEST_ID)
