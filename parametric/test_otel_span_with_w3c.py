import time

import pytest

from parametric.spec.otel_trace import SK_PRODUCER
from parametric.spec.tracecontext import get_tracecontext
from parametric.utils.test_agent import get_span
from parametric.protos.apm_test_client_pb2 import DistributedHTTPHeaders


@pytest.mark.skip_library("dotnet", "Not implemented")
@pytest.mark.skip_library("nodejs", "Not implemented")
@pytest.mark.skip_library("python", "Not implemented")
@pytest.mark.skip_library("java", "Not implemented")
def test_otel_start_span(test_agent, test_library):
    """
        - Start/end a span with start and end options
        - Start a tracer with options
    """
    test_library.otel_env = "otel_env"
    test_library.otel_service = "otel_serv"

    # entering test_otel_library starts the tracer with the above options
    with test_library:
        duration_s = int(2 * 1000000)
        start_time = int(time.time())
        with test_library.start_otel_span(
                "operation",
                span_kind=SK_PRODUCER,
                timestamp=start_time,
                new_root=True,
                attributes={"start_attr_key": "start_attr_val"},
        ) as parent:
            parent.finish(timestamp=start_time + duration_s)
    duration_ns = duration_s / (1e-9)

    root_span = get_span(test_agent)
    assert root_span["meta"]["env"] == "otel_env"
    assert root_span["service"] == "otel_serv"
    assert root_span["name"] == "operation"
    assert root_span["resource"] == "operation"
    assert root_span["meta"]["start_attr_key"] == "start_attr_val"
    assert root_span["duration"] == duration_ns


def test_otel_span_with_w3c_headers(test_agent, test_library):
    # 2) x-datadog-sampling-priority <= 0
    distributed_message = DistributedHTTPHeaders()
    for key, value in [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"]]:
        distributed_message.http_headers[key] = value

    with test_library.start_span(
            name="name", service="service", resource="resource", http_headers=distributed_message
    ) as span:
        headers = test_library.inject_headers(span.span_id).http_headers.http_headers
        # 2) x-datadog-sampling-priority <= 0
        # headers2 = make_single_request_and_get_inject_headers(
        #     test_library,
        #     [
        #         ["x-datadog-trace-id", "7890123456789012"],
        #         ["x-datadog-parent-id", "1234567890123456"],
        #         ["x-datadog-sampling-priority", "-1"],
        #     ],
        # )

    # Result: SamplingPriority = headers['x-datadog-sampling-priority'], Sampled = 0

    traceparent2, tracestate2 = get_tracecontext(headers)
    print(traceparent2, tracestate2)
    assert headers["x-datadog-sampling-priority"] == "-1"
    # assert int(b3_trace_id, base=16) == span.get("trace_id")
    # sampled2 = str(traceparent2).split("-")[3]
    # dd_items2 = tracestate2["dd"].split(";")
    # root_span = get_span(test_agent)
    # assert root_span["meta"]["env"] == "otel_env"
    # assert "traceparent" in headers
    # assert sampled2 == "00"
    # assert "tracestate" in headers
    # assert "s:-1" in dd_items2
