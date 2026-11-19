from typing import Any
from unittest.mock import Mock, patch

from utils import pytest

from tests.otel.test_tracing_otlp import OtelSpanRecord, _server_span_by_request_id
from tests.appsec.smoke_tests.utils import assert_ddot_export
from utils import features, interfaces, scenarios
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
@pytest.mark.parametrize(
    ("host", "status", "rejected", "native_id", "native_user_agent", "error"),
    [
        ("agent", 200, 0, 2, OTHER_USER_AGENT, None),  # unrelated native trace is fine
        ("agent", 503, 0, 1, USER_AGENT, "DDOT must accept"),  # failed export and native fallback
        ("agent", 200, 1, 2, OTHER_USER_AGENT, "DDOT must accept"),
        ("system-tests-collector", 200, 0, 2, OTHER_USER_AGENT, "DDOT must accept"),
        ("agent", 200, 0, 1, OTHER_USER_AGENT, "also exported via native"),  # same trace, different chunk
        ("agent", 200, 0, 2, USER_AGENT, "also exported via native"),  # fallback with a new trace ID
    ],
)
def test_security_smoke_requires_ddot_only(
    host: str, status: int, rejected: int, native_id: int, native_user_agent: str, error: str | None
) -> None:
    request = Mock(spec=HttpResponse)
    request.get_rid.return_value = REQUEST_ID
    otlp = _payload([{"traceId": "00000000000000000000000000000001", "attributes": {TEST_TAG: USER_AGENT}}])
    otlp.update(
        host=host, response={"status_code": status, "content": {"partialSuccess": {"rejectedSpans": str(rejected)}}}
    )
    native = {
        "path": "/v0.4/traces",
        "log_filename": "native.json",
        "request": {"content": [[{"trace_id": native_id, "meta": {"http.useragent": native_user_agent}}]]},
    }
    with (
        patch.object(interfaces.open_telemetry, "get_data", return_value=[otlp]),
        patch.object(interfaces.library, "get_data", return_value=[native]) as native_data,
    ):
        if error is None:
            assert_ddot_export(request)
            native_data.assert_called_once_with(path_filters=interfaces.library.trace_paths)
        else:
            with pytest.raises(AssertionError, match=error):
                assert_ddot_export(request)


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
