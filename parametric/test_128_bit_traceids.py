import pytest

from parametric.utils.headers import make_single_request_and_get_inject_headers
from parametric.utils.test_agent import get_span

parametrize = pytest.mark.parametrize
POWER_2_64 = 18446744073709551616


@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_datadog_128_bit_propagation(test_agent, test_library):
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
    assert int(headers["x-datadog-trace-id"], 10) == trace_id
    assert dd_p_tid == "640cfd8d00000000"


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("php", "Issue: Traces not available from test agent")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.skip_library("ruby", "not implemented")
@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_datadog_128_bit_propagation_tid_long(test_agent, test_library):
    """ Ensure that tid's that are too long are discarded.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["x-datadog-trace-id", "1234567890123456789"],
                ["x-datadog-parent-id", "987654321"],
                ["x-datadog-tags", "_dd.p.tid=1234567890abcdef1"],
            ],
        )
    span = get_span(test_agent)
    trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")

    assert trace_id == 1234567890123456789
    assert int(headers["x-datadog-trace-id"], 10) == trace_id
    assert dd_p_tid is None


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("php", "Issue: Traces not available from test agent")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.skip_library("ruby", "not implemented")
@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_datadog_128_bit_propagation_tid_short(test_agent, test_library):
    """ Ensure that tid's that are too short are discarded.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["x-datadog-trace-id", "1234567890123456789"],
                ["x-datadog-parent-id", "987654321"],
                ["x-datadog-tags", "_dd.p.tid=1234567890abcde"],
            ],
        )
    span = get_span(test_agent)
    trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")

    assert trace_id == 1234567890123456789
    assert int(headers["x-datadog-trace-id"], 10) == trace_id
    assert dd_p_tid is None


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("php", "Issue: Traces not available from test agent")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.skip_library("ruby", "not implemented")
@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_datadog_128_bit_propagation_tid_chars(test_agent, test_library):
    """ Ensure that tid's with bad characters are discarded.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["x-datadog-trace-id", "1234567890123456789"],
                ["x-datadog-parent-id", "987654321"],
                ["x-datadog-tags", "_dd.p.tid=1234567890abcdeg"],
            ],
        )
    span = get_span(test_agent)
    trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")

    assert trace_id == 1234567890123456789
    assert int(headers["x-datadog-trace-id"], 10) == trace_id
    assert dd_p_tid is None


@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true",}],
)
def test_datadog_128_bit_propagation_and_generation(test_agent, test_library):
    """Ensure that a new span from incoming headers does not modify the trace id when generation is true.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library, [["x-datadog-trace-id", "1234567890123456789"], ["x-datadog-parent-id", "987654321"],],
        )
    span = get_span(test_agent)
    trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")

    assert trace_id == 1234567890123456789
    assert int(headers["x-datadog-trace-id"], 10) == trace_id
    assert dd_p_tid is None


@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_datadog_128_bit_generation_disabled(test_agent, test_library):
    """Ensure that 64-bit TraceIds are properly generated, propagated in
    datadog headers, and populated in trace data.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])
    span = get_span(test_agent)
    trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")

    assert trace_id < POWER_2_64
    assert int(headers["x-datadog-trace-id"], 10) == trace_id
    assert dd_p_tid is None


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("php", "Issue: Traces not available from test agent")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.skip_library("ruby", "not implemented")
@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true",}],
)
def test_datadog_128_bit_generation_enabled(test_agent, test_library):
    """Ensure that 128-bit TraceIds are properly generated, propagated in
    datadog headers, and populated in trace data.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])
    span = get_span(test_agent)
    trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")

    assert trace_id < POWER_2_64
    assert int(headers["x-datadog-trace-id"], 10) == trace_id
    validate_dd_p_tid(dd_p_tid)


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("php", "Issue: Traces not available from test agent")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.skip_library("ruby", "not implemented")
@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "B3 single header", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_b3single_128_bit_propagation(test_agent, test_library):
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
    fields = headers["b3"].split("-", 1)

    assert trace_id == int("abcdefab12345678", 16)
    assert dd_p_tid == "640cfd8d00000000"
    check_128_bit_trace_id(fields[0], trace_id, dd_p_tid)


@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "B3 single header", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true",}],
)
def test_b3single_128_bit_propagation_and_generation(test_agent, test_library):
    """Ensure that a new span from incoming headers does not modify the trace id when generation is true.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library, [["b3", "abcdefab12345678-000000003ade68b1-1"],],
        )
    span = get_span(test_agent)
    trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")
    fields = headers["b3"].split("-", 1)

    assert trace_id == int("abcdefab12345678", 16)
    assert dd_p_tid is None
    check_64_bit_trace_id(fields[0], trace_id, dd_p_tid)


@pytest.mark.skip_library("python", "Issue: Python doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.skip_library("java", "Issue: Java doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.skip_library("ruby", "Issue: Ruby doesn't support case-insensitive distributed headers")
@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "B3 single header", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_b3single_128_bit_generation_disabled(test_agent, test_library):
    """Ensure that 64-bit TraceIds are properly generated, propagated in B3
    single-header, and populated in trace data.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])
    span = get_span(test_agent)
    fields = headers["b3"].split("-", 1)

    check_64_bit_trace_id(fields[0], span.get("trace_id"), span["meta"].get("_dd.p.tid"))


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.skip_library("ruby", "not implemented")
@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "B3 single header", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true",}],
)
def test_b3single_128_bit_generation_enabled(test_agent, test_library):
    """Ensure that 128-bit TraceIds are properly generated, propagated in B3
    single-header, and populated in trace data.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])
    span = get_span(test_agent)
    fields = headers["b3"].split("-", 1)

    check_128_bit_trace_id(fields[0], span.get("trace_id"), span["meta"].get("_dd.p.tid"))


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.skip_library("ruby", "not implemented")
@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "b3multi", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_b3multi_128_bit_propagation(test_agent, test_library):
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


@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "b3multi", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true",}],
)
def test_b3multi_128_bit_propagation_and_generation(test_agent, test_library):
    """Ensure that a new span from incoming headers does not modify the trace id when generation is true.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library, [["x-b3-traceid", "abcdefab12345678"], ["x-b3-spanid", "000000003ade68b1"],],
        )
    span = get_span(test_agent)
    trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")

    assert trace_id == int("abcdefab12345678", 16)
    assert dd_p_tid is None
    check_64_bit_trace_id(headers["x-b3-traceid"], trace_id, dd_p_tid)


@pytest.mark.skip_library("python", "Issue: Python doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.skip_library("java", "Issue: Java doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.skip_library("php", "Issue: Traces not available from test agent")
@pytest.mark.skip_library("ruby", "Issue: Ruby doesn't support case-insensitive distributed headers")
@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "b3multi", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_b3multi_128_bit_generation_disabled(test_agent, test_library):
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
@pytest.mark.skip_library("php", "Issue: Traces not available from test agent")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.skip_library("ruby", "not implemented")
@pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_PROPAGATION_STYLE": "b3multi", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true",}],
)
def test_b3multi_128_bit_generation_enabled(test_agent, test_library):
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
@pytest.mark.skip_library("php", "Issue: Traces not available from test agent")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.skip_library("ruby", "not implemented")
@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_w3c_128_bit_propagation(test_agent, test_library):
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
    fields = headers["traceparent"].split("-", 2)

    assert trace_id == int("abcdefab12345678", 16)
    assert dd_p_tid == "640cfd8d00000000"
    check_128_bit_trace_id(fields[1], trace_id, dd_p_tid)


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("php", "Issue: Traces not available from test agent")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.skip_library("ruby", "not implemented")
@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_w3c_128_bit_propagation_tid_different(test_agent, test_library):
    """Ensure that if the trace state contains a tid that is inconsistent with the trace id from
    the trace header, the trace header tid is preserved.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["traceparent", "00-640cfd8d00000000abcdefab12345678-000000003ade68b1-01"],
                ["tracestate", "dd=t.tid:640cfd8d0000ffff"],
            ],
        )
    span = get_span(test_agent)
    trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")
    fields = headers["traceparent"].split("-", 2)

    assert trace_id == int("abcdefab12345678", 16)
    assert dd_p_tid == "640cfd8d00000000"
    check_128_bit_trace_id(fields[1], trace_id, dd_p_tid)


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("php", "Issue: Traces not available from test agent")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.skip_library("ruby", "not implemented")
@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_w3c_128_bit_propagation_tid_bad(test_agent, test_library):
    """Ensure that if the trace state contains a tid that is badly formed, the trace header tid is preserved.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["traceparent", "00-640cfd8d00000000abcdefab12345678-000000003ade68b1-01"],
                ["tracestate", "dd=t.tid:640cfd8d0000XXXX"],
            ],
        )
    span = get_span(test_agent)
    trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")
    fields = headers["traceparent"].split("-", 2)

    assert trace_id == int("abcdefab12345678", 16)
    assert dd_p_tid == "640cfd8d00000000"
    check_128_bit_trace_id(fields[1], trace_id, dd_p_tid)


@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true",}],
)
def test_w3c_128_bit_propagation_and_generation(test_agent, test_library):
    """Ensure that a new span from incoming headers does not modify the trace id when generation is true.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(
            test_library, [["traceparent", "00-0000000000000000abcdefab12345678-000000003ade68b1-01",],],
        )
    span = get_span(test_agent)
    trace_id = span.get("trace_id")
    dd_p_tid = span["meta"].get("_dd.p.tid")
    fields = headers["traceparent"].split("-", 2)

    assert trace_id == int("abcdefab12345678", 16)
    assert dd_p_tid is None
    check_64_bit_trace_id(fields[1], trace_id, dd_p_tid)


@pytest.mark.skip_library("python", "Issue: Python doesn't pad the trace-id to length of 16 or 32 lower-hex characters")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("php", "Issue: Traces not available from test agent")
@pytest.mark.skip_library("ruby", "Issue: Ruby doesn't support case-insensitive distributed headers")
@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false",}],
)
def test_w3c_128_bit_generation_disabled(test_agent, test_library):
    """Ensure that 64-bit TraceIds are properly generated, propagated in W3C
    headers, and populated in trace data.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])
    span = get_span(test_agent)
    fields = headers["traceparent"].split("-", 2)

    check_64_bit_trace_id(fields[1], span.get("trace_id"), span["meta"].get("_dd.p.tid"))


@pytest.mark.skip_library("dotnet", "not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("java", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("php", "Issue: Traces not available from test agent")
@pytest.mark.skip_library("python", "not implemented")
@pytest.mark.skip_library("python_http", "not implemented")
@pytest.mark.skip_library("ruby", "not implemented")
@pytest.mark.parametrize(
    "library_env",
    [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true",}],
)
def test_w3c_128_bit_generation_enabled(test_agent, test_library):
    """Ensure that 128-bit TraceIds are properly generated, propagated in W3C
    headers, and populated in trace data.
    """
    with test_library:
        headers = make_single_request_and_get_inject_headers(test_library, [])
    span = get_span(test_agent)
    fields = headers["traceparent"].split("-", 2)

    check_128_bit_trace_id(fields[1], span.get("trace_id"), span["meta"].get("_dd.p.tid"))


ZERO8 = "00000000"
ZERO16 = ZERO8 + ZERO8


def check_64_bit_trace_id(header_trace_id, span_trace_id, dd_p_tid):
    """Ensure that 64-bit TraceIds are properly formatted and populated in
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
    # check that dd_p_tid[0:8] is a timestamp
    assert int(dd_p_tid[0:8], 16) > 0x640CFD8C
