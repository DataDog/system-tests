import pytest

from parametric.protos.apm_test_client_pb2 import DistributedHTTPHeaders
from parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from parametric.spec.trace import span_has_no_parent


@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_distributed_headers_extract_datadog(test_agent, test_library):
    """Ensure that Datadog distributed tracing headers are extracted
    and activated properly.
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
            span.set_meta(key="http.status_code", val="200")

    span = test_agent.wait_for_num_traces(num=1)[0][0]
    assert span.get("trace_id") == 123456789
    assert span.get("parent_id") == 987654321
    assert span["meta"].get(ORIGIN) == "synthetics"
    assert span["meta"].get("_dd.p.dm") == "-4"
    assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2


@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_distributed_headers_extract_datadog_invalid(test_agent, test_library):
    """Ensure that Datadog distributed tracing headers are extracted
    and activated properly.
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
def test_distributed_headers_inject_datadog(test_agent, test_library):
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
def test_distributed_headers_extractandinject_datadog(test_agent, test_library):
    """Ensure that Datadog distributed tracing headers are extracted
    and activated properly.
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
def test_distributed_headers_extractandinject_datadog_invalid(test_agent, test_library):
    """Ensure that Datadog distributed tracing headers are extracted
    and activated properly.
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


@pytest.mark.skip("needs to be implemented by tracers and test needs to adhere to RFC")
@pytest.mark.parametrize("apm_test_server_env", [{"DD_TRACE_PROPAGATION_STYLE_EXTRACT": "W3C"}])
def test_distributed_headers_extract_w3c001(apm_test_server_env, test_agent, test_library):
    """Ensure that W3C distributed tracing headers are extracted
    and activated properly.
    """

    with test_library:
        http_headers = DistributedHTTPHeaders()
        http_headers.traceparent_key = "traceparent"
        http_headers.traceparent_value = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

        with test_library.start_span(
            name="name", service="service", resource="resource", origin="synthetics", http_headers=http_headers
        ) as span:
            span.set_meta(key="http.status_code", val="200")

    span = test_agent.wait_for_num_traces(num=1)[0][0]
    assert span.get("trace_id") == 11803532876627986230
