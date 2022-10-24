import pytest

from parametric.protos.apm_test_client_pb2 import DistributedHTTPHeaders
from parametric.spec.trace import SAMPLING_PRIORITY_KEY


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
def test_distributed_headers_extract_datadog(test_agent, test_library):
    """Ensure that Datadog distributed tracing headers are extracted
    and activated properly.
    """
    with test_library:
        distributed_message = DistributedHTTPHeaders()
        distributed_message.http_headers["x-datadog-trace-id"] = "12345"
        distributed_message.http_headers["x-datadog-parent-id"] = "123"

        with test_library.start_span(
            name="name", service="service", resource="resource", origin="synthetics", http_headers=distributed_message
        ) as span:
            span.set_meta(key="http.status_code", val="200")

    span = get_span(test_agent)
    assert span.get("trace_id") == 12345
    assert span.get("parent_id") == 123


@pytest.mark.skip_library("dotnet", "not impemented")
@pytest.mark.skip_library("golang", "not impemented")
@pytest.mark.skip_library("nodejs", "not impemented")
def test_distributed_headers_inject_datadog(test_agent, test_library):
    """Ensure that Datadog distributed tracing headers are injected properly.
    """
    with test_library:
        with test_library.start_span(name="name") as span:
            headers = test_library.inject_headers().http_headers.http_headers
    span = get_span(test_agent)
    assert span.get("trace_id") == int(headers["x-datadog-trace-id"])
    assert span.get("span_id") == int(headers["x-datadog-parent-id"])
    assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == int(headers["x-datadog-sampling-priority"])


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

    span = get_span(test_agent)
    assert span.get("trace_id") == 11803532876627986230


def get_span(test_agent):
    traces = test_agent.traces()
    span = traces[0][0]
    return span
