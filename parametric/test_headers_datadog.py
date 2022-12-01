import pytest

from parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from parametric.spec.trace import span_has_no_parent
from parametric.utils.headers import make_single_request_and_get_headers
from parametric.utils.test_agent import get_span


@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_headers_datadog_extract_valid(test_agent, test_library):
    """Ensure that Datadog distributed tracing headers are extracted
    and activated properly.
    """
    with test_library:
        headers = make_single_request_and_get_headers(
            test_library,
            [
                ["x-datadog-trace-id", "123456789"],
                ["x-datadog-parent-id", "987654321"],
                ["x-datadog-sampling-priority", "2"],
                ["x-datadog-origin", "synthetics;,=web"],
                ["x-datadog-tags", "_dd.p.dm=-4"],
            ],
        )

    span = get_span(test_agent)
    assert span.get("trace_id") == 123456789
    assert span.get("parent_id") == 987654321
    assert span["meta"].get(ORIGIN) == "synthetics;,=web"
    assert span["meta"].get("_dd.p.dm") == "-4"
    assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2


@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_headers_datadog_extract_invalid(test_agent, test_library):
    """Ensure that invalid Datadog distributed tracing headers are not extracted.
    """
    with test_library:
        headers = make_single_request_and_get_headers(
            test_library,
            [
                ["x-datadog-trace-id", "0"],
                ["x-datadog-parent-id", "0"],
                ["x-datadog-sampling-priority", "2"],
                ["x-datadog-origin", "synthetics"],
                ["x-datadog-tags", "_dd.p.dm=-4"],
            ],
        )

    span = get_span(test_agent)
    assert span.get("trace_id") != 0
    assert span_has_no_parent(span)
    # assert span["meta"].get(ORIGIN) is None # TODO: Determine if we keep x-datadog-origin for an invalid trace-id/parent-id
    assert span["meta"].get("_dd.p.dm") != "-4"
    assert span["metrics"].get(SAMPLING_PRIORITY_KEY) != 2


@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_headers_datadog_inject_valid(test_agent, test_library):
    """Ensure that Datadog distributed tracing headers are injected properly.
    """
    with test_library:
        headers = make_single_request_and_get_headers(test_library, [])

    span = get_span(test_agent)
    assert int(headers["x-datadog-trace-id"]) == span.get("trace_id")
    assert int(headers["x-datadog-parent-id"]) == span.get("span_id")
    assert int(headers["x-datadog-sampling-priority"]) == span["metrics"].get(SAMPLING_PRIORITY_KEY)


@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_headers_datadog_propagate_valid(test_agent, test_library):
    """Ensure that Datadog distributed tracing headers are extracted
    and injected properly.
    """
    with test_library:
        headers = make_single_request_and_get_headers(
            test_library,
            [
                ["x-datadog-trace-id", "123456789"],
                ["x-datadog-parent-id", "987654321"],
                ["x-datadog-sampling-priority", "2"],
                ["x-datadog-origin", "synthetics"],
                ["x-datadog-tags", "_dd.p.dm=-4"],
            ],
        )

    span = get_span(test_agent)
    assert headers["x-datadog-trace-id"] == "123456789"
    assert headers["x-datadog-parent-id"] != "987654321"
    assert headers["x-datadog-sampling-priority"] == "2"
    assert headers["x-datadog-origin"] == "synthetics"
    assert "_dd.p.dm=-4" in headers["x-datadog-tags"]


@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_headers_datadog_propagate_invalid(test_agent, test_library):
    """Ensure that invalid Datadog distributed tracing headers are not extracted
    and the new span context is injected properly.
    """
    with test_library:
        headers = make_single_request_and_get_headers(
            test_library,
            [
                ["x-datadog-trace-id", "0"],
                ["x-datadog-parent-id", "0"],
                ["x-datadog-sampling-priority", "2"],
                ["x-datadog-origin", "synthetics"],
                ["x-datadog-tags", "_dd.p.dm=-4"],
            ],
        )

    assert headers["x-datadog-trace-id"] != "0"
    assert headers["x-datadog-parent-id"] != "0"
    assert headers["x-datadog-sampling-priority"] != "2"
    # assert headers["x-datadog-origin"] == '' # TODO: Determine if we keep x-datadog-origin for an invalid trace-id/parent-id
    assert "_dd.p.dm=-4" not in headers["x-datadog-tags"]
