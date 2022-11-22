from typing import Any

import pytest

from parametric.protos.apm_test_client_pb2 import DistributedHTTPHeaders
from parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN

parametrize = pytest.mark.parametrize

def enable_b3() -> Any:
    env1 = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "B3 SINGLE HEADER",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "b3 single header",
    }
    env2 = {
        "DD_TRACE_PROPAGATION_STYLE": "B3 single header",
    }
    return parametrize("library_env", [env1, env2])

@enable_b3()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_headers_b3_extract_valid(test_agent, test_library):
    """Ensure that b3 distributed tracing headers are extracted
    and activated properly.
    """
    with test_library:
        distributed_message = DistributedHTTPHeaders()
        distributed_message.http_headers["b3"] = "000000000000000000000000075bcd15-000000003ade68b1-1"

        with test_library.start_span(
            name="name", service="service", resource="resource", http_headers=distributed_message
        ) as span:
            span.set_meta(key="http.status_code", val="200")

    span = get_span(test_agent)
    assert span.get("trace_id") == 123456789
    assert span.get("parent_id") == 987654321
    assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 1
    assert span["meta"].get(ORIGIN) is None

@enable_b3()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_headers_b3_extract_invalid(test_agent, test_library):
    """Ensure that invalid b3 distributed tracing headers are not extracted.
    """
    with test_library:
        distributed_message = DistributedHTTPHeaders()
        distributed_message.http_headers["b3"] = "0-0-1"

        with test_library.start_span(
            name="name", service="service", resource="resource", http_headers=distributed_message
        ) as span:
            span.set_meta(key="http.status_code", val="200")

    span = get_span(test_agent)
    assert span.get("trace_id") != 0
    assert span.get("parent_id") != 0
    assert span["meta"].get(ORIGIN) is None

@enable_b3()
@pytest.mark.skip_library("golang", "not impemented")
@pytest.mark.skip_library("nodejs", "not impemented")
def test_headers_b3_inject_valid(test_agent, test_library):
    """Ensure that b3 distributed tracing headers are injected properly.
    """
    with test_library:
        with test_library.start_span(name="name") as span:
            headers = test_library.inject_headers(span.span_id).http_headers.http_headers

    span = get_span(test_agent)
    b3Arr = headers["b3"].split('-')
    b3_trace_id = b3Arr[0]
    b3_span_id = b3Arr[1]
    b3_sampling = b3Arr[2]

    assert len(b3_trace_id) == 16 or len(b3_trace_id) == 32
    assert int(b3_trace_id, base=16) == span.get("trace_id")
    assert int(b3_span_id, base=16) == span.get("span_id") and len(b3_span_id) == 16
    assert b3_sampling == "1" if span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0 else "0"
    assert span["meta"].get(ORIGIN) is None

@enable_b3()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_headers_b3multi_propagate_valid(test_agent, test_library):
    """Ensure that b3 distributed tracing headers are extracted
    and injected properly.
    """
    with test_library:
        distributed_message = DistributedHTTPHeaders()
        distributed_message.http_headers["b3"] = "000000000000000000000000075bcd15-000000003ade68b1-1"

        with test_library.start_span(
            name="name", service="service", resource="resource", http_headers=distributed_message
        ) as span:
            headers = test_library.inject_headers(span.span_id).http_headers.http_headers

    span = get_span(test_agent)
    b3Arr = headers["b3"].split('-')
    b3_trace_id = b3Arr[0]
    b3_span_id = b3Arr[1]
    b3_sampling = b3Arr[2]

    assert len(b3_trace_id) == 16 or len(b3_trace_id) == 32
    assert int(b3_trace_id, base=16) == span.get("trace_id")
    assert int(b3_span_id, base=16) == span.get("span_id") and len(b3_span_id) == 16
    assert b3_sampling == "1"
    assert span["meta"].get(ORIGIN) is None

@enable_b3()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_headers_b3multi_propagate_invalid(test_agent, test_library):
    """Ensure that invalid b3 distributed tracing headers are not extracted
    and the new span context is injected properly.
    """
    with test_library:
        distributed_message = DistributedHTTPHeaders()
        distributed_message.http_headers["b3"] = "0-0-1"

        with test_library.start_span(
            name="name", service="service", resource="resource", http_headers=distributed_message
        ) as span:
            headers = test_library.inject_headers(span.span_id).http_headers.http_headers

    span = get_span(test_agent)
    assert span.get("trace_id") != 0
    assert span.get("span_id") != 0

    b3Arr = headers["b3"].split('-')
    b3_trace_id = b3Arr[0]
    b3_span_id = b3Arr[1]
    b3_sampling = b3Arr[2]

    assert len(b3_trace_id) == 16 or len(b3_trace_id) == 32
    assert int(b3_trace_id, base=16) == span.get("trace_id")
    assert int(b3_span_id, base=16) == span.get("span_id") and len(b3_span_id) == 16
    assert b3_sampling == "1" if span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0 else "0"
    assert span["meta"].get(ORIGIN) is None

def get_span(test_agent):
    traces = test_agent.traces()
    span = traces[0][0]
    return span
