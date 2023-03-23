from typing import Any

import pytest

from parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from parametric.spec.trace import span_has_no_parent
from parametric.utils.headers import make_single_request_and_get_inject_headers
from parametric.utils.test_agent import get_span

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
@pytest.mark.skip_library("ruby", "Ruby doesn't support case-insensitive distributed headers")
def test_headers_b3_extract_valid(test_agent, test_library):
    """Ensure that b3 distributed tracing headers are extracted
    and activated properly.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library, [["b3", "000000000000000000000000075bcd15-000000003ade68b1-1"]]
        )

    span = get_span(test_agent)
    assert span.get("trace_id") == 123456789
    assert span.get("parent_id") == 987654321
    assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 1
    assert span["meta"].get(ORIGIN) is None


@enable_b3()
def test_headers_b3_extract_invalid(test_agent, test_library):
    """Ensure that invalid b3 distributed tracing headers are not extracted.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [["b3", "0-0-1"]])

    span = get_span(test_agent)
    assert span.get("trace_id") != 0
    assert span_has_no_parent(span)
    assert span["meta"].get(ORIGIN) is None


@enable_b3()
@pytest.mark.skip_library("python", "Issue: Python doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.skip_library("java", "Issue: Java doesn't pad the span-id to length of 16 lower-hex characters")
@pytest.mark.skip_library("ruby", "Ruby doesn't support case-insensitive distributed headers")
def test_headers_b3_inject_valid(test_agent, test_library):
    """Ensure that b3 distributed tracing headers are injected properly.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])

    span = get_span(test_agent)
    b3Arr = headers["b3"].split("-")
    b3_trace_id = b3Arr[0]
    b3_span_id = b3Arr[1]
    b3_sampling = b3Arr[2]

    assert len(b3_trace_id) == 16 or len(b3_trace_id) == 32
    assert int(b3_trace_id, base=16) == span.get("trace_id")
    assert int(b3_span_id, base=16) == span.get("span_id") and len(b3_span_id) == 16
    assert b3_sampling == "1" if span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0 else "0"
    assert span["meta"].get(ORIGIN) is None


@enable_b3()
@pytest.mark.skip_library("python", "Issue: Python doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.skip_library("java", "Issue: Java doesn't pad the span-id to length of 16 lower-hex characters")
@pytest.mark.skip_library("ruby", "Ruby doesn't support case-insensitive distributed headers")
def test_headers_b3multi_propagate_valid(test_agent, test_library):
    """Ensure that b3 distributed tracing headers are extracted
    and injected properly.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library, [["b3", "000000000000000000000000075bcd15-000000003ade68b1-1"]]
        )

    span = get_span(test_agent)
    b3Arr = headers["b3"].split("-")
    b3_trace_id = b3Arr[0]
    b3_span_id = b3Arr[1]
    b3_sampling = b3Arr[2]

    assert len(b3_trace_id) == 16 or len(b3_trace_id) == 32
    assert int(b3_trace_id, base=16) == span.get("trace_id")
    assert int(b3_span_id, base=16) == span.get("span_id") and len(b3_span_id) == 16
    assert b3_sampling == "1"
    assert span["meta"].get(ORIGIN) is None


@enable_b3()
@pytest.mark.skip_library("python", "Issue: Python doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.skip_library("java", "Issue: Java doesn't pad the span-id to length of 16 lower-hex characters")
@pytest.mark.skip_library("ruby", "Ruby doesn't support case-insensitive distributed headers")
def test_headers_b3multi_propagate_invalid(test_agent, test_library):
    """Ensure that invalid b3 distributed tracing headers are not extracted
    and the new span context is injected properly.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [["b3", "0-0-1"]])

    span = get_span(test_agent)
    assert span.get("trace_id") != 0
    assert span.get("span_id") != 0

    b3Arr = headers["b3"].split("-")
    b3_trace_id = b3Arr[0]
    b3_span_id = b3Arr[1]
    b3_sampling = b3Arr[2]

    assert len(b3_trace_id) == 16 or len(b3_trace_id) == 32
    assert int(b3_trace_id, base=16) == span.get("trace_id")
    assert int(b3_span_id, base=16) == span.get("span_id") and len(b3_span_id) == 16
    assert b3_sampling == "1" if span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0 else "0"
    assert span["meta"].get(ORIGIN) is None
