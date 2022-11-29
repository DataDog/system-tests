import pytest

from parametric.protos.apm_test_client_pb2 import DistributedHTTPHeaders
from parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from parametric.spec.trace import span_has_no_parent


@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_distributed_headers_extract_datadog_D001(test_agent, test_library):
    """Ensure that Datadog distributed tracing headers are extracted
    and activated properly.
    """
    with test_library:
        distributed_message = DistributedHTTPHeaders()
        distributed_message.http_headers["x-datadog-trace-id"] = "123456789"
        distributed_message.http_headers["x-datadog-parent-id"] = "987654321"
        distributed_message.http_headers["x-datadog-sampling-priority"] = "2"
        distributed_message.http_headers["x-datadog-origin"] = "synthetics,=web"
        distributed_message.http_headers["x-datadog-tags"] = "_dd.p.dm=-4"

        with test_library.start_span(
            name="name", service="service", resource="resource", http_headers=distributed_message
        ) as span:
            span.set_meta(key="http.status_code", val="200")

    span = test_agent.wait_for_num_traces(num=1)[0][0]
    assert span.get("trace_id") == 123456789
    assert span.get("parent_id") == 987654321
    assert span["meta"].get(ORIGIN) == "synthetics,=web"
    assert span["meta"].get("_dd.p.dm") == "-4"
    assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2


@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_distributed_headers_extract_datadog_invalid_D002(test_agent, test_library):
    """Ensure that invalid Datadog distributed tracing headers are not extracted.
    """
    with test_library:
        distributed_message = DistributedHTTPHeaders()
        distributed_message.http_headers["x-datadog-trace-id"] = "0"
        distributed_message.http_headers["x-datadog-parent-id"] = "0"
        distributed_message.http_headers["x-datadog-sampling-priority"] = "2"
        distributed_message.http_headers["x-datadog-origin"] = "synthetics"
        distributed_message.http_headers["x-datadog-tags"] = "_dd.p.dm=-4"

        with test_library.start_span(
            name="name", service="service", resource="resource", http_headers=distributed_message
        ) as span:
            span.set_meta(key="http.status_code", val="200")

    span = test_agent.wait_for_num_traces(num=1)[0][0]
    assert span.get("trace_id") != 0
    assert span_has_no_parent(span)
    # assert span["meta"].get(ORIGIN) is None # TODO: Determine if we keep x-datadog-origin for an invalid trace-id/parent-id
    assert span["meta"].get("_dd.p.dm") != "-4"
    assert span["metrics"].get(SAMPLING_PRIORITY_KEY) != 2


@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_distributed_headers_inject_datadog_D003(test_agent, test_library):
    """Ensure that Datadog distributed tracing headers are injected properly.
    """
    with test_library:
        with test_library.start_span(name="name") as span:
            headers = test_library.inject_headers(span.span_id).http_headers.http_headers
    span = test_agent.wait_for_num_traces(num=1)[0][0]
    assert int(headers["x-datadog-trace-id"]) == span.get("trace_id")
    assert int(headers["x-datadog-parent-id"]) == span.get("span_id")
    assert int(headers["x-datadog-sampling-priority"]) == span["metrics"].get(SAMPLING_PRIORITY_KEY)


@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_distributed_headers_propagate_datadog_D004(test_agent, test_library):
    """Ensure that Datadog distributed tracing headers are extracted
    and injected properly.
    """
    with test_library:
        distributed_message = DistributedHTTPHeaders()
        distributed_message.http_headers["x-datadog-trace-id"] = "123456789"
        distributed_message.http_headers["x-datadog-parent-id"] = "987654321"
        distributed_message.http_headers["x-datadog-sampling-priority"] = "2"
        distributed_message.http_headers["x-datadog-origin"] = "synthetics"
        distributed_message.http_headers["x-datadog-tags"] = "_dd.p.dm=-4"

        with test_library.start_span(
            name="name", service="service", resource="resource", http_headers=distributed_message
        ) as span:
            headers = test_library.inject_headers(span.span_id).http_headers.http_headers

    span = test_agent.wait_for_num_traces(num=1)[0][0]
    assert headers["x-datadog-trace-id"] == "123456789"
    assert headers["x-datadog-parent-id"] != "987654321"
    assert headers["x-datadog-sampling-priority"] == "2"
    assert headers["x-datadog-origin"] == "synthetics"
    assert "_dd.p.dm=-4" in headers["x-datadog-tags"]


@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_distributed_headers_extractandinject_datadog_invalid_D005(test_agent, test_library):
    """Ensure that invalid Datadog distributed tracing headers are not extracted
    and the new span context is injected properly.
    """
    with test_library:
        distributed_message = DistributedHTTPHeaders()
        distributed_message.http_headers["x-datadog-trace-id"] = "0"
        distributed_message.http_headers["x-datadog-parent-id"] = "0"
        distributed_message.http_headers["x-datadog-sampling-priority"] = "2"
        distributed_message.http_headers["x-datadog-origin"] = "synthetics"
        distributed_message.http_headers["x-datadog-tags"] = "_dd.p.dm=-4"

        with test_library.start_span(
            name="name", service="service", resource="resource", http_headers=distributed_message
        ) as span:
            headers = test_library.inject_headers(span.span_id).http_headers.http_headers

    span = test_agent.wait_for_num_traces(num=1)[0][0]
    assert headers["x-datadog-trace-id"] != "0"
    assert headers["x-datadog-parent-id"] != "0"
    assert headers["x-datadog-sampling-priority"] != "2"
    # assert headers["x-datadog-origin"] == '' # TODO: Determine if we keep x-datadog-origin for an invalid trace-id/parent-id
    assert "_dd.p.dm=-4" not in headers["x-datadog-tags"]

def get_span(test_agent):
    traces = test_agent.traces()
    span = traces[0][0]
    return span
