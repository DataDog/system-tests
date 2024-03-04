import json

import pytest

from ddapm_test_agent.trace import Span, root_span

from utils import bug, missing_feature, irrelevant, context, scenarios, features
from utils.parametric.spec.otel_trace import SK_INTERNAL, SK_SERVER, OtelSpan
from utils.parametric.spec.trace import find_trace_by_root, find_span

# this global mark applies to all tests in this file.
#   DD_TRACE_OTEL_ENABLED=true is required in the tracers to enable OTel
#   CORECLR_ENABLE_PROFILING=1 is required in .NET to enable auto-instrumentation
pytestmark = pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_OTEL_ENABLED": "true", "CORECLR_ENABLE_PROFILING": "1",}],
)

TEST_TRACE_ID = "ff0000000000051791e0000000000041"
TEST_SPAN_ID = "ff00000000000516"
TEST_TRACESTATE = "dd=t.dm:-0"
TEST_ATTRIBUTES = {"arg1": "val1"}


@features.f_interoperability
@scenarios.parametric
class Test_Otel_SDK_Interoperability:
    @staticmethod
    def assert_span_link(trace):
        assert len(trace) == 1
        root = root_span(trace)
        span_links = json.loads(root["meta"]["_dd.span_links"])
        assert len(span_links) == 1
        link = span_links[0]
        assert link["trace_id"] == TEST_TRACE_ID
        assert link["span_id"] == TEST_SPAN_ID
        assert link["trace_state"] == TEST_TRACESTATE
        assert link["attributes"] == {"arg1": "val1", "_dd.p.dm": "-0"}

    def test_set_update_remove_meta(self, test_agent, test_library):
        """
            - Test that meta is set/updated/removed across APIs
        """
        with test_library:
            with test_library.start_span("dd_span") as dd_span:
                dd_span.set_meta("arg1", "val1")
                dd_span.set_meta("arg2", "val2")

                otel_span = test_library.otel_current_span()

                otel_span.set_attribute("arg3", "val3")
                otel_span.set_attribute("arg4", "val4")

                dd_span.set_meta("arg3", None)  # Remove the arg3/val3 pair (Created with the Otel API)
                assert dd_span.get_meta("arg3") is None
                assert otel_span.get_attribute("arg3") is None

                otel_span.set_attribute("arg1", None)  # Remove the arg1/val1 pair (Created with the DD API)
                assert dd_span.get_meta("arg1") is None
                assert otel_span.get_attribute("arg1") is None

                otel_span.set_attribute("arg2", "val3")  # Update the arg2/val2 pair (Created with the DD API)
                assert dd_span.get_meta("arg2") == "val3"
                assert otel_span.get_attribute("arg2") == "val3"

                dd_span.set_meta("arg4", "val5")  # Update the arg4/val4 pair (Created with the Otel API)
                assert dd_span.get_meta("arg4") == "val5"
                assert otel_span.get_attribute("arg4") == "val5"

                dd_span.finish()

                # The following calls should have no effect
                otel_span.set_attribute("arg5", "val5")  # Set a meta with the Otel API
                otel_span.set_attribute("arg2", "val4")  # Update the arg2/val2 pair (Created with the DD API)
                otel_span.set_attribute("arg2", None)  # Remove the arg2/val2 pair (Created with the DD API)

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace_by_root(traces, Span(name="dd_span"))
        assert len(trace) == 1

        dd_span = root_span(trace)
        meta = dd_span["meta"]

        # Span-life changes
        assert "arg1" not in meta
        assert meta["arg2"] == "val3"
        assert "arg3" not in meta
        assert meta["arg4"] == "val5"

        # Afterlife changes
        assert "arg5" not in meta

    def test_set_update_remove_metric(self, test_agent, test_library):
        """
            - Test that metrics are set/updated/removed across APIs
        """
        with test_library:
            with test_library.start_span("dd_span") as dd_span:
                dd_span.set_metric("m1", 1)  # Set a metric with the DD API
                dd_span.set_metric("m2", 2)

                otel_span = test_library.otel_current_span()

                otel_span.set_attribute("m3", 3)  # Set a metric with the Otel API
                otel_span.set_attribute("m4", 4)

                dd_span.set_metric("m3", None)  # Remove the m3/3 pair (Created with the Otel API)
                assert dd_span.get_metric("m3") is None
                assert otel_span.get_attribute("m3") is None

                otel_span.set_attribute("m1", None)  # Remove the m1/1 pair (Created with the DD API)
                assert dd_span.get_metric("m1") is None
                assert otel_span.get_attribute("m1") is None

                otel_span.set_attribute("m2", 3)  # Update the m2/2 pair (Created with the DD API)
                assert dd_span.get_metric("m2") == 3
                assert otel_span.get_attribute("m2") == 3

                dd_span.set_metric("m4", 5)  # Update the m4/4 pair (Created with the Otel API)
                assert dd_span.get_metric("m4") == 5
                assert otel_span.get_attribute("m4") == 5

                dd_span.finish()

                # The following calls should have no effect
                otel_span.set_attribute("m5", 5)  # Set a metric with the Otel API
                otel_span.set_attribute("m2", 4)  # Update the m2/2 pair (Created with the DD API)
                otel_span.set_attribute("m2", None)  # Remove the m2/2 pair (Created with the DD API)

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace_by_root(traces, Span(name="dd_span"))
        assert len(trace) == 1

        dd_span = root_span(trace)
        metrics = dd_span["metrics"]

        # Span-life changes
        assert "m1" not in metrics
        assert metrics["m2"] == 3
        assert "m3" not in metrics
        assert metrics["m4"] == 5

        # Afterlife changes
        assert "m5" not in metrics

    def test_update_resource(self, test_agent, test_library):
        """
            - Test that the resource is updated across APIs
        """
        with test_library:
            with test_library.otel_start_span("my_resource") as otel_span:
                dd_span = test_library.current_span()

                dd_span.set_resource("my_new_resource")
                assert dd_span.get_resource() == "my_new_resource"
                assert otel_span.get_name() == "my_new_resource"

                otel_span.set_name("my_new_resource2")
                assert dd_span.get_resource() == "my_new_resource2"
                assert otel_span.get_name() == "my_new_resource2"

                dd_span.finish()

                otel_span.set_name("my_new_resource3")
                assert dd_span.get_resource() == "my_new_resource2"
                assert otel_span.get_name() == "my_new_resource2"

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace_by_root(traces, OtelSpan(resource="my_new_resource2"))
        assert len(trace) == 1

    def test_span_links_basic(self, test_agent, test_library):
        """
            - Test that links set on a span created with the Datadog API are updated into the OTel API
        """
        with test_library:
            with test_library.start_span("dd.span") as dd_span:
                dd_span.add_link(
                    parent_id=0,
                    attributes=TEST_ATTRIBUTES,
                    http_headers=[
                        ("traceparent", f"00-{TEST_TRACE_ID}-{TEST_SPAN_ID}-01"),
                        ("tracestate", TEST_TRACESTATE),
                    ],
                )

                otel_span = test_library.otel_current_span()

                otel_span_links = otel_span.get_links()
                assert len(otel_span_links) == 1

                otel_link = otel_span_links[0]
                assert otel_link["trace_id"] == TEST_TRACE_ID
                assert otel_link["parent_id"] == TEST_SPAN_ID
                assert otel_link["tracestate"] == TEST_TRACESTATE
                assert otel_link["attributes"] == {"arg1": "val1", "_dd.p.dm": "-0"}

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace_by_root(traces, Span(name="dd.span"))
        self.assert_span_link(trace)

    def test_span_links_add(self, test_agent, test_library):
        """
            - Test that links set on a span created with the OTel API are updated into the Datadog API
        """
        with test_library:
            with test_library.otel_start_span("otel.span") as otel_span:
                current_span = test_library.current_span()

                current_span.add_link(
                    parent_id=0,
                    attributes=TEST_ATTRIBUTES,
                    http_headers=[
                        ("traceparent", f"00-{TEST_TRACE_ID}-{TEST_SPAN_ID}-01"),
                        ("tracestate", TEST_TRACESTATE),
                    ],
                )

                otel_span_links = otel_span.get_links()
                assert len(otel_span_links) == 1

                otel_link = otel_span_links[0]
                assert otel_link["trace_id"] == TEST_TRACE_ID
                assert otel_link["parent_id"] == TEST_SPAN_ID
                assert otel_link["tracestate"] == TEST_TRACESTATE
                assert otel_link["attributes"] == {"arg1": "val1", "_dd.p.dm": "-0"}

                otel_span.end_span()

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace_by_root(traces, Span(name="dd.span"))
        self.assert_span_link(trace)

    def test_set_attribute_from_datadog(self, test_agent, test_library):
        """
            - Test that attributes set using the Datadog API are visible in the OTel API
        """
        with test_library:
            with test_library.start_span(name="dd_span") as dd_span:
                dd_span.set_meta("int", 1)
                dd_span.set_meta("float", 1.0)
                dd_span.set_meta("bool", True)
                dd_span.set_meta("str", "string")
                dd_span.set_meta("none", None)
                # Note: OTel's arrays MUST be homogeneous
                dd_span.set_meta("str_array", ["a", "b", "c"])
                dd_span.set_meta("nested_str_array", [["a", "b"], ["c", "d"]])
                dd_span.set_meta("int_array", [1, 2, 3])

                otel_span = test_library.otel_current_span()
                assert otel_span.get_attribute("int") == 1
                assert otel_span.get_attribute("float") == 1.0
                assert otel_span.get_attribute("bool") == True
                assert otel_span.get_attribute("str") == "string"
                assert otel_span.get_attribute("none") == None
                assert otel_span.get_attribute("str_array") == ["a", "b", "c"]
                assert otel_span.get_attribute("nested_str_array") == [["a", "b"], ["c", "d"]]
                assert otel_span.get_attribute("int_array") == [1, 2, 3]

    def test_set_attribute_from_otel(self, test_agent, test_library):
        """
            - Test that attributes set using the OTel API are visible in the Datadog API
        """
        with test_library:
            with test_library.otel_start_span(name="otel_span") as otel_span:
                otel_span.set_attribute("int", 1)
                otel_span.set_attribute("float", 1.0)
                otel_span.set_attribute("bool", True)
                otel_span.set_attribute("str", "string")
                otel_span.set_attribute("none", None)
                # Note: OTel's arrays MUST be homogeneous
                otel_span.set_attribute("str_array", ["a", "b", "c"])
                otel_span.set_attribute("nested_str_array", [["a", "b"], ["c", "d"]])
                otel_span.set_attribute("int_array", [1, 2, 3])

                dd_span = test_library.current_span()
                assert dd_span.get_metric("int") == 1
                assert dd_span.get_metric("float") == 1.0
                assert dd_span.get_meta("bool") == True
                assert dd_span.get_meta("str") == "string"
                assert dd_span.get_meta("none") == None
                assert dd_span.get_meta("str_array") == ["a", "b", "c"]
                assert dd_span.get_meta("nested_str_array") == [["a", "b"], ["c", "d"]]
                assert dd_span.get_metric("int_array") == [1, 2, 3]
