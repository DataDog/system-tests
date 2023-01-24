from typing import Any

import pytest

from parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from parametric.spec.trace import span_has_no_parent
from parametric.utils.headers import make_single_request_and_get_inject_headers
from parametric.utils.test_agent import get_span

parametrize = pytest.mark.parametrize


def enable_b3multi() -> Any:
    env1 = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "B3MULTI",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "b3multi",
    }
    env2 = {
        "DD_TRACE_PROPAGATION_STYLE": "b3multi",
    }
    env3 = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "B3",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "b3",
    }
    env4 = {
        "DD_TRACE_PROPAGATION_STYLE": "B3",
    }
    return parametrize("library_env", [env1, env2, env3, env4])


@enable_b3multi()
@pytest.mark.skip_library("dotnet", "Latest release does not implement new configuration")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "TODO: remove when https://github.com/DataDog/dd-trace-js/pull/2477 lands")
def test_headers_b3multi_extract_valid(test_agent, test_library):
    """Ensure that b3multi distributed tracing headers are extracted
    and activated properly.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["x-b3-traceid", "000000000000000000000000075bcd15"],
                ["x-b3-spanid", "000000003ade68b1"],
                ["x-b3-sampled", "1"],
            ],
        )

    span = get_span(test_agent)
    assert span.get("trace_id") == 123456789
    assert span.get("parent_id") == 987654321
    assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 1
    assert span["meta"].get(ORIGIN) is None


@enable_b3multi()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "TODO: remove when https://github.com/DataDog/dd-trace-js/pull/2477 lands")
def test_headers_b3multi_extract_invalid(test_agent, test_library):
    """Ensure that invalid b3multi distributed tracing headers are not extracted.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library, [["x-b3-traceid", "0"], ["x-b3-spanid", "0"], ["x-b3-sampled", "1"],]
        )

    span = get_span(test_agent)
    assert span.get("trace_id") != 0
    assert span_has_no_parent(span)
    assert span["meta"].get(ORIGIN) is None


@enable_b3multi()
@pytest.mark.skip_library("dotnet", "Latest release does not implement new configuration")
@pytest.mark.skip_library("python", "Issue: Python doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.skip_library("golang", "not impemented")
@pytest.mark.skip_library("nodejs", "TODO: remove when https://github.com/DataDog/dd-trace-js/pull/2477 lands")
def test_headers_b3multi_inject_valid(test_agent, test_library):
    """Ensure that b3multi distributed tracing headers are injected properly.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])

    span = get_span(test_agent)
    b3_trace_id = headers["x-b3-traceid"]
    b3_span_id = headers["x-b3-spanid"]
    b3_sampling = headers["x-b3-sampled"]

    assert len(b3_trace_id) == 16 or len(b3_trace_id) == 32
    assert int(b3_trace_id, base=16) == span.get("trace_id")
    assert int(b3_span_id, base=16) == span.get("span_id") and len(b3_span_id) == 16
    assert b3_sampling == "1" if span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0 else "0"
    assert span["meta"].get(ORIGIN) is None


@enable_b3multi()
@pytest.mark.skip_library("dotnet", "Latest release does not implement new configuration")
@pytest.mark.skip_library("python", "Issue: Python doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "TODO: remove when https://github.com/DataDog/dd-trace-js/pull/2477 lands")
def test_headers_b3multi_propagate_valid(test_agent, test_library):
    """Ensure that b3multi distributed tracing headers are extracted
    and injected properly.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["x-b3-traceid", "000000000000000000000000075bcd15"],
                ["x-b3-spanid", "000000003ade68b1"],
                ["x-b3-sampled", "1"],
            ],
        )

    span = get_span(test_agent)
    b3_trace_id = headers["x-b3-traceid"]
    b3_span_id = headers["x-b3-spanid"]
    b3_sampling = headers["x-b3-sampled"]

    assert len(b3_trace_id) == 16 or len(b3_trace_id) == 32
    assert int(b3_trace_id, base=16) == span.get("trace_id")
    assert int(b3_span_id, base=16) == span.get("span_id") and len(b3_span_id) == 16
    assert b3_sampling == "1"
    assert span["meta"].get(ORIGIN) is None


@enable_b3multi()
@pytest.mark.skip_library("dotnet", "Latest release does not implement new configuration")
@pytest.mark.skip_library("python", "Issue: Python doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "TODO: remove when https://github.com/DataDog/dd-trace-js/pull/2477 lands")
def test_headers_b3multi_propagate_invalid(test_agent, test_library):
    """Ensure that invalid b3multi distributed tracing headers are not extracted
    and the new span context is injected properly.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library, [["x-b3-traceid", "0"], ["x-b3-spanid", "0"], ["x-b3-sampled", "1"],]
        )

    span = get_span(test_agent)
    assert span.get("trace_id") != 0
    assert span.get("span_id") != 0

    b3_trace_id = headers["x-b3-traceid"]
    b3_span_id = headers["x-b3-spanid"]
    b3_sampling = headers["x-b3-sampled"]

    assert len(b3_trace_id) == 16 or len(b3_trace_id) == 32
    assert int(b3_trace_id, base=16) == span.get("trace_id")
    assert int(b3_span_id, base=16) == span.get("span_id") and len(b3_span_id) == 16
    assert b3_sampling == "1" if span["metrics"].get(SAMPLING_PRIORITY_KEY) > 0 else "0"
    assert span["meta"].get(ORIGIN) is None
