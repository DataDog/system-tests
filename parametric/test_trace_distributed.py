import pytest

from parametric.protos.apm_test_client_pb2 import DistributedHTTPHeaders


# @parametrize("apm_test_server_env", [{"": "0"}])
# @all_libs()
# def test_metrics_computed_after_span_finish_TS010(
#     apm_test_server_env, apm_test_server_factory, test_agent, test_client
# ):
#     """
#     When DD_TRACE_STATS_COMPUTATION_ENABLED=False
#         Metrics must be computed after spans are finished, otherwise components of the aggregation key may change after
#         contribution to aggregates.
#     """

#     with test_client:
#         http_headers = DistributedHTTPHeaders()
#         http_headers.x_datadog_trace_id_key = "12321311232"

#         with test_client.start_span(name="name", service="service", resource="resource", origin="synthetics", http_headers=http_headers) as span:
#             span.set_meta(key="http.status_code", val="200")

#     requests = test_agent.v06_stats_requests()
#     assert len(requests) == 0, "No stats were computed"


def test_distributed_headers_extract_datadog(test_agent, test_client):
    """Ensure that Datadog distributed tracing headers are extracted
    and activated properly.
    """

    with test_client:
        http_headers = DistributedHTTPHeaders()
        http_headers.x_datadog_trace_id_key = "x-datadog-trace-id"
        http_headers.x_datadog_trace_id_value = "12345"
        http_headers.x_datadog_parent_id_key = "x-datadog-parent-id"
        http_headers.x_datadog_parent_id_value = "123"

        with test_client.start_span(
            name="name", service="service", resource="resource", origin="synthetics", http_headers=http_headers
        ) as span:
            span.set_meta(key="http.status_code", val="200")

    span = get_span(test_agent)
    assert span.get("trace_id") == 12345
    assert span.get("parent_id") == 123


@pytest.mark.parametrize("apm_test_server_env", [{"DD_TRACE_PROPAGATION_STYLE_EXTRACT": "W3C"}])
def test_distributed_headers_extract_w3c001(apm_test_server_env, test_agent, test_client):
    """
    """

    with test_client:
        http_headers = DistributedHTTPHeaders()
        http_headers.traceparent_key = "traceparent"
        http_headers.traceparent_value = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

        with test_client.start_span(
            name="name", service="service", resource="resource", origin="synthetics", http_headers=http_headers
        ) as span:
            span.set_meta(key="http.status_code", val="200")

    span = get_span(test_agent)
    assert span.get("trace_id") == 11803532876627986230


# @pytest.mark.parametrize(
#     "apm_test_server_env", [{"DD_TRACE_PROPAGATION_STYLE_INJECT": "W3C"}]
# )
# @all_libs()
# def test_distributed_headers_inject_w3c001(
#     apm_test_server_env, apm_test_server_factory, test_agent, test_client
# ):
#     """
#     """

#     with test_client:
#         http_headers = DistributedHTTPHeaders()
#         with test_client.start_span(name="name", service="service", resource="resource", origin="synthetics") as span:
#             span.set_meta(key="http.status_code", val="200")
#             test_client.inject_span(span, http_headers)
#     traceparent = http_headers["traceparent"]
#     span = get_span(test_agent)
#     test_inject_w3c(span, traceparent)


def get_span(test_agent):
    traces = test_agent.traces()
    span = traces[0][0]
    return span


def test_inject_w3c(span, traceparent, expected_version="00", expected_trace_flags="01"):
    version, trace_id, span_id, trace_flags = traceparent.split("-")

    assert span.trace_id == int(trace_id[-16:], 16)
    assert span.span_id == int(span_id[-16:], 16)
    assert version == expected_version
    assert trace_flags == expected_trace_flags
