import pytest

from parametric.utils.headers import make_single_request_and_get_inject_headers
from parametric.utils.test_agent import get_span

parametrize = pytest.mark.parametrize


@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_datadog_128_bit_propagation_D001(test_agent, test_library):
    """ Ensure that external 128-bit TraceIds are properly propagated in Datadog
    headers.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["x-datadog-trace-id", "1234567890123456789"],
                ["x-datadog-parent-id", "987654321"],
                ["x-datadog-tags", "_dd.p.tid=640cfd8d00000000"],
            ],
        )

    span = get_span(test_agent)
    trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")

    assert trace_id == 1234567890123456789
    validate_dd_p_tid(dd_p_tid)
    assert dd_p_tid == "640cfd8d00000000"


@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_datadog_128_bit_generation_disabled_D002(test_agent, test_library):
    """Ensure that 64-bit TraceIds are properly generated, propagated in
    datadog headers, and populated in trace data.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])

    header_trace_id = headers["x-datadog-trace-id"]
    span = get_span(test_agent)
    span_trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")

    # Note: length of 2^64-1 encoded as decimal is 20.
    assert len(header_trace_id) < 21
    assert int(header_trace_id, 10) == span_trace_id
    assert dd_p_tid is None


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true",}],
)
def test_datadog128_bit_generation_enabled_D003(test_agent, test_library):
    """Ensure that 128-bit TraceIds are properly generated, propagated in
    datadog headers, and populated in trace data.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])
    header_trace_id = headers["x-datadog-trace-id"]
    span = get_span(test_agent)
    span_trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")

    assert len(header_trace_id) < 21
    assert int(header_trace_id, 10) == span_trace_id
    validate_dd_p_tid(dd_p_tid)


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "B3 single header", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_b3single_128_bit_propagation_D004(test_agent, test_library):
    """Ensure that external 128-bit TraceIds are properly propagated in B3
    single-header.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library, [["b3", "640cfd8d00000000abcdefab12345678-000000003ade68b1-1"],],
        )
    span = get_span(test_agent)
    trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")
    b3 = headers["b3"]

    assert trace_id == int("abcdefab12345678", 16)
    assert dd_p_tid == "640cfd8d00000000"
    assert len(b3) > 32 + 16
    check_128_bit_trace_id(b3[0:32], trace_id, dd_p_tid)


@pytest.mark.skip_library("python", "Issue: Python doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.skip_library("java", "Issue: Java doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "B3 single header", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_b3single_128_bit_generation_disabled_D005(test_agent, test_library):
    """Ensure that 64-bit TraceIds are properly generated, propagated in B3
    single-header, and populated in trace data.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])
    span = get_span(test_agent)
    b3 = headers["b3"]

    assert len(b3) > 16 + 16
    check_64_bit_trace_id(b3[0:16], span.get("trace_id"), span["meta"].get("_dd.p.tid"))


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "B3 single header", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true",}],
)
def test_b3single128_bit_generation_enabled_D006(test_agent, test_library):
    """Ensure that 128-bit TraceIds are properly generated, propagated in B3
    single-header, and populated in trace data.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])
    span = get_span(test_agent)
    b3 = headers["b3"]

    assert len(b3) > 32 + 16
    check_128_bit_trace_id(b3[0:32], span.get("trace_id"), span["meta"].get("_dd.p.tid"))


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "b3multi", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_b3multi_128_bit_propagation_D007(test_agent, test_library):
    """Ensure that external 128-bit TraceIds are properly propagated in B3
    multi-headers.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library, [["x-b3-traceid", "640cfd8d00000000abcdefab12345678"], ["x-b3-spanid", "000000003ade68b1"],],
        )
    span = get_span(test_agent)
    trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")

    assert trace_id == int("abcdefab12345678", 16)
    assert dd_p_tid == "640cfd8d00000000"
    check_128_bit_trace_id(headers["x-b3-traceid"], trace_id, dd_p_tid)


@pytest.mark.skip_library("python", "Issue: Python doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.skip_library("java", "Issue: Java doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "b3multi", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_b3multi_128_bit_generation_disabled_D008(test_agent, test_library):
    """Ensure that 64-bit TraceIds are properly generated, propagated in B3
    multi-headers, and populated in trace data.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])
    span = get_span(test_agent)
    check_64_bit_trace_id(headers["x-b3-traceid"], span.get("trace_id"), span["meta"].get("_dd.p.tid"))


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "b3multi", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true",}],
)
def test_b3multi128_bit_generation_enabled_D009(test_agent, test_library):
    """Ensure that 128-bit TraceIds are properly generated, propagated in B3
    multi-headers, and populated in trace data.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])
    span = get_span(test_agent)
    check_128_bit_trace_id(headers["x-b3-traceid"], span.get("trace_id"), span["meta"].get("_dd.p.tid"))


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_w3c_128_bit_propagation_D010(test_agent, test_library):
    """Ensure that external 128-bit TraceIds are properly propagated in W3C
    headers.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library, [["traceparent", "00-640cfd8d00000000abcdefab12345678-000000003ade68b1-01",],],
        )
    span = get_span(test_agent)
    trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")
    traceparent = headers["traceparent"]

    assert trace_id == int("abcdefab12345678", 16)
    assert dd_p_tid == "640cfd8d00000000"
    assert len(traceparent) == 55
    check_128_bit_trace_id(traceparent[3:35], trace_id, dd_p_tid)


@pytest.mark.skip_library("python", "Issue: Python doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_w3c_128_bit_generation_disabled_D011(test_agent, test_library):
    """Ensure that 64-bit TraceIds are properly generated, propagated in W3C
    headers, and populated in trace data.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])
    span = get_span(test_agent)
    traceparent = headers["traceparent"]

    assert len(traceparent) == 55
    check_64_bit_trace_id(traceparent[3:35], span.get("trace_id"), span["meta"].get("_dd.p.tid"))


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true",}],
)
def test_w3c128_bit_generation_enabled_D012(test_agent, test_library):
    """Ensure that 128-bit TraceIds are properly generated, propagated in W3C
    headers, and populated in trace data.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])
    span = get_span(test_agent)
    traceparent = headers["traceparent"]

    assert len(traceparent) == 55
    check_128_bit_trace_id(traceparent[3:35], span.get("trace_id"), span["meta"].get("_dd.p.tid"))


ZERO8 = "00000000"
ZERO16 = ZERO8 + ZERO8


def check_64_bit_trace_id(header_trace_id, span_trace_id, dd_p_tid):
    """Ensure that 128-bit TraceIds are properly formatted and populated in
    trace data.
    """
    assert len(header_trace_id) == 16 or (len(header_trace_id) == 32 and header_trace_id[0:16] == ZERO16)
    assert int(header_trace_id, 16) == span_trace_id
    assert dd_p_tid is None


def check_128_bit_trace_id(header_trace_id, span_trace_id, dd_p_tid):
    """Ensure that 128-bit TraceIds are well-formed and populated in trace
    data.
    """
    assert len(header_trace_id) == 32
    assert header_trace_id[8:16] == ZERO8
    assert int(header_trace_id[16:32], 16) == span_trace_id
    validate_dd_p_tid(dd_p_tid)
    assert header_trace_id.startswith(dd_p_tid)


def validate_dd_p_tid(dd_p_tid):
    """Validate that dd_p_tid is well-formed.
    """
    assert not dd_p_tid is None
    assert len(dd_p_tid) == 16
    assert dd_p_tid != ZERO16
    assert dd_p_tid[8:16] == ZERO8
    # add check that dd_p_tid[0:8] is a timestamp
    assert int(dd_p_tid[0:8], 16) > 0x640CFD8C
