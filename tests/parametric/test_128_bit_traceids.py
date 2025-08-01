import pytest

from utils.parametric.spec.trace import find_first_span_in_trace_payload, find_trace, find_only_span
from utils import missing_feature, irrelevant, context, scenarios, features
from .conftest import APMLibrary

parametrize = pytest.mark.parametrize
POWER_2_64 = 18446744073709551616


@scenarios.parametric
@features.trace_id_128_bit_generation_propagation
class Test_128_Bit_Traceids:
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false"}],
    )
    def test_datadog_128_bit_propagation(self, test_agent, test_library: APMLibrary):
        """Ensure that external 128-bit TraceIds are properly propagated in Datadog
        headers.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "1234567890123456789"),
                    ("x-datadog-parent-id", "987654321"),
                    ("x-datadog-tags", "_dd.p.tid=640cfd8d00000000"),
                ],
            )
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")

        assert trace_id == 1234567890123456789
        assert int(headers["x-datadog-trace-id"], 10) == trace_id
        assert dd_p_tid == "640cfd8d00000000"
        assert "_dd.p.tid=" + dd_p_tid in headers["x-datadog-tags"]

    @missing_feature(context.library < "nodejs@5.38.0", reason="Implemented in 5.38.0")
    @missing_feature(context.library == "ruby", reason="not implemented")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false"}],
    )
    def test_datadog_128_bit_propagation_tid_long(self, test_agent, test_library):
        """Ensure that incoming tids that are too long are discarded."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "1234567890123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-tags", "_dd.p.tid=1234567890abcdef1"],
                ],
            )
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")

        assert trace_id == 1234567890123456789
        assert int(headers["x-datadog-trace-id"], 10) == trace_id
        assert dd_p_tid is None
        assert "x-datadog-tags" not in headers or "_dd.p.tid=" not in headers["x-datadog-tags"]

    @missing_feature(context.library < "nodejs@5.38.0", reason="Implemented in 5.38.0")
    @missing_feature(context.library == "ruby", reason="not implemented")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false"}],
    )
    def test_datadog_128_bit_propagation_tid_short(self, test_agent, test_library):
        """Ensure that incoming tids that are too short are discarded."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "1234567890123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-tags", "_dd.p.tid=1234567890abcde"],
                ],
            )
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")

        assert trace_id == 1234567890123456789
        assert int(headers["x-datadog-trace-id"], 10) == trace_id
        assert dd_p_tid is None
        assert "x-datadog-tags" not in headers or "_dd.p.tid=" not in headers["x-datadog-tags"]

    @missing_feature(context.library < "nodejs@5.38.0", reason="Implemented in 5.38.0")
    @missing_feature(context.library == "ruby", reason="not implemented")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false"}],
    )
    def test_datadog_128_bit_propagation_tid_chars(self, test_agent, test_library):
        """Ensure that incoming tids with bad characters are discarded."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "1234567890123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-tags", "_dd.p.tid=1234567890abcdeX"],
                ],
            )
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")

        assert trace_id == 1234567890123456789
        assert int(headers["x-datadog-trace-id"], 10) == trace_id
        assert dd_p_tid is None
        assert "x-datadog-tags" not in headers or "_dd.p.tid=" not in headers["x-datadog-tags"]

    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true"}],
    )
    def test_datadog_128_bit_propagation_and_generation(self, test_agent, test_library):
        """Ensure that a new span from incoming headers does not modify the trace id when generation is true."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [["x-datadog-trace-id", "1234567890123456789"], ["x-datadog-parent-id", "987654321"]],
            )
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")

        assert trace_id == 1234567890123456789
        assert int(headers["x-datadog-trace-id"], 10) == trace_id
        assert dd_p_tid is None
        assert "x-datadog-tags" not in headers or "_dd.p.tid=" not in headers["x-datadog-tags"]

    @missing_feature(context.library == "rust", reason="128 bit traceid is always enabled")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false"}],
    )
    def test_datadog_128_bit_generation_disabled(self, test_agent, test_library):
        """Ensure that 64-bit TraceIds are properly generated, propagated in
        datadog headers, and populated in trace data.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([])
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")

        assert trace_id < POWER_2_64
        assert int(headers["x-datadog-trace-id"], 10) == trace_id
        assert dd_p_tid is None
        assert "x-datadog-tags" not in headers or "_dd.p.tid=" not in headers["x-datadog-tags"]

    @missing_feature(context.library == "rust", reason="APMSP-2059")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "Datadog", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true"}],
    )
    def test_datadog_128_bit_generation_enabled(self, test_agent, test_library):
        """Ensure that 128-bit TraceIds are properly generated, propagated in
        datadog headers, and populated in trace data.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([])
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")

        assert trace_id < POWER_2_64
        assert int(headers["x-datadog-trace-id"], 10) == trace_id
        assert "_dd.p.tid=" + dd_p_tid in headers["x-datadog-tags"]
        validate_dd_p_tid(dd_p_tid)

    @missing_feature(context.library < "java@1.24.0", reason="Implemented in 1.24.0")
    @missing_feature(context.library < "nodejs@4.19.0", reason="Implemented in 4.19.0 & 3.40.0")
    @missing_feature(context.library == "rust", reason="APMSP-2059")
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_PROPAGATION_STYLE": "Datadog"}])
    def test_datadog_128_bit_generation_enabled_by_default(self, test_agent, test_library):
        """Ensure that 128-bit TraceIds are properly generated, propagated in
        datadog headers, and populated in trace data.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([])
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")

        assert trace_id < POWER_2_64
        assert int(headers["x-datadog-trace-id"], 10) == trace_id
        assert "_dd.p.tid=" + dd_p_tid in headers["x-datadog-tags"]
        validate_dd_p_tid(dd_p_tid)

    @missing_feature(context.library == "cpp", reason="propagation style not supported")
    @missing_feature(context.library == "rust", reason="propagation style not supported")
    @irrelevant(
        context.library in ("ruby", "python"),
        reason="Supports the value `b3` instead of the deprecated `B3 single header`",
    )
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "B3 single header", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false"}],
    )
    def test_b3single_128_bit_propagation(self, test_agent, test_library):
        """Ensure that external 128-bit TraceIds are properly propagated in B3
        single-header.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [["b3", "640cfd8d00000000abcdefab12345678-000000003ade68b1-1"]],
            )
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")
        fields = headers["b3"].split("-", 1)

        assert trace_id == int("abcdefab12345678", 16)
        assert dd_p_tid == "640cfd8d00000000"
        check_128_bit_trace_id(fields[0], trace_id, dd_p_tid)

    @missing_feature(context.library == "cpp", reason="propagation style not supported")
    @missing_feature(context.library == "rust", reason="propagation style not supported")
    @irrelevant(
        context.library in ("ruby", "python"),
        reason="Supports the value `b3` instead of the deprecated `B3 single header`",
    )
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "B3 single header", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true"}],
    )
    def test_b3single_128_bit_propagation_and_generation(self, test_agent, test_library):
        """Ensure that a new span from incoming headers does not modify the trace id when generation is true."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([["b3", "abcdefab12345678-000000003ade68b1-1"]])
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")
        fields = headers["b3"].split("-", 1)

        assert trace_id == int("abcdefab12345678", 16)
        assert dd_p_tid is None
        check_64_bit_trace_id(fields[0], trace_id, dd_p_tid)

    @missing_feature(context.library == "cpp", reason="propagation style not supported")
    @missing_feature(context.library == "rust", reason="propagation style not supported")
    @irrelevant(
        context.library in ("ruby", "python"),
        reason="Supports the value `b3` instead of the deprecated `B3 single header`",
    )
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "B3 single header", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false"}],
    )
    def test_b3single_128_bit_generation_disabled(self, test_agent, test_library):
        """Ensure that 64-bit TraceIds are properly generated, propagated in B3
        single-header, and populated in trace data.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([])
        span = find_only_span(test_agent.wait_for_num_traces(1))
        fields = headers["b3"].split("-", 1)

        check_64_bit_trace_id(fields[0], span.get("trace_id"), span["meta"].get("_dd.p.tid"))

    @missing_feature(context.library == "cpp", reason="propagation style not supported")
    @missing_feature(context.library == "rust", reason="propagation style not supported")
    @irrelevant(
        context.library in ("ruby", "python"),
        reason="Supports the value `b3` instead of the deprecated `B3 single header`",
    )
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "B3 single header", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true"}],
    )
    def test_b3single_128_bit_generation_enabled(self, test_agent, test_library):
        """Ensure that 128-bit TraceIds are properly generated, propagated in B3
        single-header, and populated in trace data.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([])
        span = find_only_span(test_agent.wait_for_num_traces(1))
        fields = headers["b3"].split("-", 1)

        check_128_bit_trace_id(fields[0], span.get("trace_id"), span["meta"].get("_dd.p.tid"))

    @missing_feature(context.library == "rust", reason="propagation style not supported")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "b3multi", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false"}],
    )
    def test_b3multi_128_bit_propagation(self, test_agent, test_library):
        """Ensure that external 128-bit TraceIds are properly propagated in B3
        multi-headers.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [["x-b3-traceid", "640cfd8d00000000abcdefab12345678"], ["x-b3-spanid", "000000003ade68b1"]],
            )
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")

        assert trace_id == int("abcdefab12345678", 16)
        assert dd_p_tid == "640cfd8d00000000"
        check_128_bit_trace_id(headers["x-b3-traceid"], trace_id, dd_p_tid)

    @missing_feature(context.library == "rust", reason="propagation style not supported")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "b3multi", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true"}],
    )
    def test_b3multi_128_bit_propagation_and_generation(self, test_agent, test_library):
        """Ensure that a new span from incoming headers does not modify the trace id when generation is true."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [["x-b3-traceid", "abcdefab12345678"], ["x-b3-spanid", "000000003ade68b1"]],
            )
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")

        assert trace_id == int("abcdefab12345678", 16)
        assert dd_p_tid is None
        check_64_bit_trace_id(headers["x-b3-traceid"], trace_id, dd_p_tid)

    @missing_feature(context.library == "rust", reason="propagation style not supported")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "b3multi", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false"}],
    )
    def test_b3multi_128_bit_generation_disabled(self, test_agent, test_library):
        """Ensure that 64-bit TraceIds are properly generated, propagated in B3
        multi-headers, and populated in trace data.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([])
        span = find_only_span(test_agent.wait_for_num_traces(1))

        check_64_bit_trace_id(headers["x-b3-traceid"], span.get("trace_id"), span["meta"].get("_dd.p.tid"))

    @missing_feature(context.library == "rust", reason="propagation style not supported")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "b3multi", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true"}],
    )
    def test_b3multi_128_bit_generation_enabled(self, test_agent, test_library):
        """Ensure that 128-bit TraceIds are properly generated, propagated in B3
        multi-headers, and populated in trace data.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([])
        span = find_only_span(test_agent.wait_for_num_traces(1))

        check_128_bit_trace_id(headers["x-b3-traceid"], span.get("trace_id"), span["meta"].get("_dd.p.tid"))

    @missing_feature(context.library == "rust", reason="APMSP-2059")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false"}],
    )
    def test_w3c_128_bit_propagation(self, test_agent, test_library):
        """Ensure that external 128-bit TraceIds are properly propagated in W3C
        headers.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [["traceparent", "00-640cfd8d00000000abcdefab12345678-000000003ade68b1-01"]],
            )
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")
        fields = headers["traceparent"].split("-", 2)

        assert trace_id == int("abcdefab12345678", 16)
        assert dd_p_tid == "640cfd8d00000000"
        check_128_bit_trace_id(fields[1], trace_id, dd_p_tid)

    @missing_feature(context.library < "nodejs@5.7.0", reason="implemented in 5.7.0 & 4.31.0")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false"}],
    )
    def test_w3c_128_bit_propagation_tid_consistent(self, test_agent, test_library):
        """Ensure that if the trace state contains a tid that is consistent with the trace id from
        the trace header then no error is reported.
        """
        with test_library:
            test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-640cfd8d00000000abcdefab12345678-000000003ade68b1-01"],
                    ["tracestate", "dd=t.tid:640cfd8d00000000"],
                ],
            )
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")
        propagation_error = span["meta"].get("_dd.propagation_error")

        assert trace_id == int("abcdefab12345678", 16)
        assert dd_p_tid == "640cfd8d00000000"
        assert propagation_error is None

    @irrelevant(
        context.library == "ruby",
        reason="ruby tracer adds trace level tags to the local root span and not the chunk root span. This inconsistency is not a bug and is expected.",
    )
    @missing_feature(context.library == "rust", reason="APMSP-2059")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true"}],
    )
    def test_w3c_128_bit_propagation_tid_in_chunk_root(self, test_agent, test_library):
        """Ensure that root span contains the tid."""
        with (
            test_library,
            test_library.dd_start_span(name="parent", service="service", resource="resource") as parent,
            test_library.dd_start_span(name="child", service="service", parent_id=parent.span_id),
        ):
            pass

        traces = test_agent.wait_for_num_traces(1, clear=True, sort_by_start=False)
        trace = find_trace(traces, parent.trace_id)
        assert len(trace) == 2
        first_span = find_first_span_in_trace_payload(trace)
        tid_chunk_root = first_span["meta"].get("_dd.p.tid")
        assert tid_chunk_root is not None

    @missing_feature(context.library == "rust", reason="APMSP-2059")
    def test_w3c_128_bit_propagation_tid_in_trace_chunk(self, test_agent, test_library):
        """Ensure that atleast one span in the trace chunk contains the tid."""
        with (
            test_library,
            test_library.dd_start_span(name="parent", service="service", resource="resource") as parent,
            test_library.dd_start_span(name="child", service="service", parent_id=parent.span_id),
        ):
            pass

        traces = test_agent.wait_for_num_traces(1, clear=True, sort_by_start=False)
        trace = find_trace(traces, parent.trace_id)
        assert len(trace) == 2

        for span in trace:
            tid = span["meta"].get("_dd.p.tid")
            if tid is not None:
                break
        else:
            raise AssertionError(f"No span in the trace chunk contains the tid: {traces}")

    @missing_feature(context.library < "nodejs@5.38.0", reason="Implemented in 5.38.0")
    @missing_feature(context.library == "rust", reason="APMSP-2059")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false"}],
    )
    def test_w3c_128_bit_propagation_tid_inconsistent(self, test_agent, test_library):
        """Ensure that if the trace state contains a tid that is inconsistent with the trace id from
        the trace header, the trace header tid is preserved.
        """
        with test_library:
            test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-640cfd8d00000000abcdefab12345678-000000003ade68b1-01"],
                    ["tracestate", "dd=t.tid:640cfd8d0000ffff"],
                ],
            )
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")

        assert trace_id == int("abcdefab12345678", 16)
        assert dd_p_tid == "640cfd8d00000000"

    @missing_feature(context.library < "nodejs@5.38.0", reason="Implemented in 5.38.0")
    @missing_feature(context.library == "rust", reason="APMSP-2059")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false"}],
    )
    def test_w3c_128_bit_propagation_tid_malformed(self, test_agent, test_library):
        """Ensure that if the trace state contains a tid that is badly formed, the trace header tid is preserved."""
        with test_library:
            test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-640cfd8d00000000abcdefab12345678-000000003ade68b1-01"],
                    ["tracestate", "dd=t.tid:XXXX"],
                ],
            )
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")

        assert trace_id == int("abcdefab12345678", 16)
        assert dd_p_tid == "640cfd8d00000000"

    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true"}],
    )
    def test_w3c_128_bit_propagation_and_generation(self, test_agent, test_library):
        """Ensure that a new span from incoming headers does not modify the trace id when generation is true."""
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [["traceparent", "00-0000000000000000abcdefab12345678-000000003ade68b1-01"]],
            )
        span = find_only_span(test_agent.wait_for_num_traces(1))
        trace_id = span.get("trace_id")
        dd_p_tid = span["meta"].get("_dd.p.tid")
        fields = headers["traceparent"].split("-", 2)

        assert trace_id == int("abcdefab12345678", 16)
        assert dd_p_tid is None
        check_64_bit_trace_id(fields[1], trace_id, dd_p_tid)

    @missing_feature(context.library == "rust", reason="128 bit traceid is always enabled")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "false"}],
    )
    def test_w3c_128_bit_generation_disabled(self, test_agent, test_library):
        """Ensure that 64-bit TraceIds are properly generated, propagated in W3C
        headers, and populated in trace data.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([])
        span = find_only_span(test_agent.wait_for_num_traces(1))
        fields = headers["traceparent"].split("-", 2)

        check_64_bit_trace_id(fields[1], span.get("trace_id"), span["meta"].get("_dd.p.tid"))

    @missing_feature(context.library == "rust", reason="APMSP-2059")
    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext", "DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED": "true"}],
    )
    def test_w3c_128_bit_generation_enabled(self, test_agent, test_library):
        """Ensure that 128-bit TraceIds are properly generated, propagated in W3C
        headers, and populated in trace data.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers([])
        span = find_only_span(test_agent.wait_for_num_traces(1))
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
    """Validate that dd_p_tid is well-formed."""
    assert dd_p_tid is not None
    assert len(dd_p_tid) == 16
    assert dd_p_tid != ZERO16
    assert dd_p_tid[8:16] == ZERO8
    # check that dd_p_tid[0:8] is consistent with a  Unix timestamp from after
    # 17:15:40 March 11, 2023.
    assert int(dd_p_tid[0:8], 16) > 0x640CFD8C
