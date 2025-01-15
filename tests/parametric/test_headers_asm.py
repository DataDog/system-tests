from typing import Any

import pytest

from utils.parametric.spec.trace import find_span_in_traces
from utils import scenarios, features
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY


@scenarios.parametric
@features.asm_headers_propagation
class Test_Headers_ASM:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_EXPERIMENTAL_APPSEC_STANDALONE_ENABLED": "true",
                "DD_APPSEC_ENABLED": "true",
            },
        ],
    )
    def test_asm_standalone_extract_headers(self, test_agent, test_library):
        with test_library:
            with test_library.dd_start_span(name="extract_headers") as s:
                headers = test_library.dd_extract_headers(s.span_id)
        
        trace = test_agent.wait_for_num_traces(1)
        span = find_span_in_traces(trace, s.trace_id, s.span_id)
        assert span["name"] == "extract_headers"
        assert "x-datadog-tags" in headers
        assert "_dd.p.appsec" in headers["x-datadog-tags"]

        assert "tracestate" in headers
        # tags that start with _dd.p. are stored as t. in tracestate to save space
        assert "t.appsec" in headers["tracestate"]

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_PROPAGATION_STYLE": "tracecontext,datadog",
                "DD_EXPERIMENTAL_APPSEC_STANDALONE_ENABLED": "true",
                "DD_APPSEC_ENABLED": "true",
            },
            {
                "DD_TRACE_PROPAGATION_STYLE": "datadog,tracecontext",
                "DD_EXPERIMENTAL_APPSEC_STANDALONE_ENABLED": "true",
                "DD_APPSEC_ENABLED": "true",
            },
        ],
    )
    def test_asm_standalone_tracecontext_datadog(self, test_agent, test_library):
        with test_library:
            with test_library.dd_extract_headers_and_make_child_span(
                "identical_trace_info",
                [
                    ["traceparent", "00-11111111111111110000000000000001-000000003ade68b1-00"],
                    ["tracestate", "dd=s:0;p:000000003ade68b1;t.appsec:1,foo=1"],
                    ["x-datadog-trace-id", "1"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111,_dd.p.appsec=1"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "0"],
                ],
            ) as s1:
                pass

        trace = test_agent.wait_for_num_traces(1)
        span = find_span_in_traces(trace, s1.trace_id, s1.span_id)
        span["name"] = "identical_trace_info"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert "_dd.p.appsec" in span["meta"]

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_PROPAGATION_STYLE": "tracecontext,datadog",
                "DD_EXPERIMENTAL_APPSEC_STANDALONE_ENABLED": "true",
                "DD_APPSEC_ENABLED": "true",
            },
            {
                "DD_TRACE_PROPAGATION_STYLE": "datadog,tracecontext",
                "DD_EXPERIMENTAL_APPSEC_STANDALONE_ENABLED": "true",
                "DD_APPSEC_ENABLED": "true",
            },
        ],
    )
    def test_asm_standalone_tracecontext_datadog_without_appsec_tag(self, test_agent, test_library):
        with test_library:
            with test_library.dd_extract_headers_and_make_child_span(
                "identical_trace_info",
                [
                    ["traceparent", "00-11111111111111110000000000000001-000000003ade68b1-00"],
                    ["tracestate", "dd=s:0;p:000000003ade68b1,foo=1"],
                    ["x-datadog-trace-id", "1"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "0"],
                ],
            ) as s1:
                pass

        trace = test_agent.wait_for_num_traces(1)
        span = find_span_in_traces(trace, s1.trace_id, s1.span_id)
        span["name"] = "identical_trace_info"
        assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == 0

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_PROPAGATION_STYLE": "datadog,tracecontext",  # default
                "DD_EXPERIMENTAL_APPSEC_STANDALONE_ENABLED": "true",
                "DD_APPSEC_ENABLED": "true",
            },
        ],
    )
    def test_asm_standalone_single_headers(self, test_agent, test_library):
        with test_library:
            with test_library.dd_extract_headers_and_make_child_span(
                "tracecontext_only",
                [
                    ["traceparent", "00-11111111111111110000000000000001-000000003ade68b1-00"],
                    ["tracestate", "dd=s:0;p:000000003ade68b1;t.appsec:1,foo=1"],
                ],
            ) as s1:
                pass

            with test_library.dd_extract_headers_and_make_child_span(
                "datadog_only",
                [
                    ["x-datadog-trace-id", "2"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111,_dd.p.appsec=1"],
                    ["x-datadog-parent-id", "123456789"],
                    ["x-datadog-sampling-priority", "0"],
                ],
            ) as s2:
                pass

        traces = test_agent.wait_for_num_traces(2)
        span1 = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        assert span1["name"] == "tracecontext_only"
        assert span1["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert "_dd.p.appsec" in span1["meta"]

        span2 = find_span_in_traces(traces, s2.trace_id, s2.span_id)
        assert span2["name"] == "datadog_only"
        assert span2["metrics"].get(SAMPLING_PRIORITY_KEY) == 2
        assert "_dd.p.appsec" in span2["meta"]

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_PROPAGATION_STYLE": "datadog,tracecontext",  # default
                "DD_EXPERIMENTAL_APPSEC_STANDALONE_ENABLED": "true",
                "DD_APPSEC_ENABLED": "true",
            },
        ],
    )
    def test_asm_standalone_single_headers_without_appsec_tag(self, test_agent, test_library):
        with test_library:
            with test_library.dd_extract_headers_and_make_child_span(
                "tracecontext_only",
                [
                    ["traceparent", "00-11111111111111110000000000000001-000000003ade68b1-00"],
                    ["tracestate", "dd=s:0;p:000000003ade68b1,foo=1"],
                ],
            ) as s1:
                pass

            with test_library.dd_extract_headers_and_make_child_span(
                "datadog_only",
                [
                    ["x-datadog-trace-id", "2"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111"],
                    ["x-datadog-parent-id", "123456789"],
                    ["x-datadog-sampling-priority", "0"],
                ],
            ) as s2:
                pass

        traces = test_agent.wait_for_num_traces(2)
        span1 = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        assert span1["name"] == "tracecontext_only"
        assert span1["metrics"].get(SAMPLING_PRIORITY_KEY) == 0

        span2 = find_span_in_traces(traces, s2.trace_id, s2.span_id)
        assert span2["name"] == "datadog_only"
        assert span2["metrics"].get(SAMPLING_PRIORITY_KEY) == 0
