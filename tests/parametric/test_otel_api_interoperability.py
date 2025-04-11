import pytest

from utils import scenarios, features
from opentelemetry.trace import SpanKind
from utils.parametric.spec.trace import find_trace, find_span, retrieve_span_links, find_only_span, find_root_span
from utils.parametric._library_client import APMLibrary

# this global mark applies to all tests in this file.
#   DD_TRACE_OTEL_ENABLED=true is required in the tracers to enable OTel
pytestmark = pytest.mark.parametrize("library_env", [{"DD_TRACE_OTEL_ENABLED": "true"}])

TEST_TRACE_ID = "ff0000000000051791e0000000000041"
TEST_TRACE_ID_HIGH = 18374686479671624983  # ff00000000000517
TEST_TRACE_ID_LOW = 10511401530282737729  # 91e0000000000041
TEST_SPAN_ID = "ff00000000000516"
TEST_SPAN_ID_INT = 18374686479671624982  # ff00000000000516
TEST_TRACESTATE = "dd=t.dm:-0"
TEST_ATTRIBUTES = {"arg1": "val1"}


@features.f_otel_interoperability
@scenarios.parametric
class Test_Otel_API_Interoperability:
    def test_span_creation_using_otel(self, test_agent, test_library):
        """- A span created with the OTel API should be visible in the DD API"""
        with test_library, test_library.otel_start_span("otel_span") as otel_span:
            dd_current_span = test_library.dd_current_span()

            assert dd_current_span is not None
            assert dd_current_span.span_id == otel_span.span_id

    def test_span_creation_using_datadog(self, test_agent, test_library):
        """- A span created with the DD API should be visible in the OTel API"""
        with test_library, test_library.dd_start_span("dd_span") as dd_span:
            otel_current_span = test_library.otel_current_span()

            assert otel_current_span is not None
            assert otel_current_span.span_id == dd_span.span_id

    def test_otel_start_after_datadog_span(self, test_agent, test_library):
        """- Start a span using the OTel API while a span created using the Datadog API already exists"""
        with test_library:
            with (
                test_library.dd_start_span("dd_span") as dd_span,
                test_library.otel_start_span(
                    name="otel_span", span_kind=SpanKind.INTERNAL, parent_id=dd_span.span_id
                ) as otel_span,
            ):
                current_dd_span = test_library.dd_current_span()
                otel_context = otel_span.span_context()

                # FIXME: The trace_id is encoded in hex while span_id is an int. Make this API consistent
                assert current_dd_span.trace_id == otel_context.get("trace_id")
                assert f"{int(current_dd_span.span_id):016x}" == otel_context.get("span_id")
            dd_span.finish()

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, dd_span.trace_id)
        assert len(trace) == 2

        root = find_root_span(trace)
        span = find_span(trace, otel_span.span_id)
        assert root is not None
        assert span is not None
        assert span.get("resource") == "otel_span"
        assert span.get("parent_id") == root.get("span_id")

    def test_has_ended(self, test_agent, test_library):
        """- Test that the ending status of a span is propagated across APIs"""
        with test_library, test_library.dd_start_span("dd_span") as dd_span:
            dd_current_span = test_library.otel_current_span()
            dd_current_span.is_recording()

            has_ended = dd_current_span.is_recording()
            assert has_ended is True

            dd_span.finish()

            has_ended = dd_current_span.is_recording()
            assert has_ended is False

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, dd_span.trace_id)
        assert len(trace) == 1

    def test_datadog_start_after_otel_span(self, test_agent, test_library):
        """- Start a span using the Datadog API while a span created using the OTel API already exists"""
        with test_library, test_library.otel_start_span(name="otel_span", span_kind=SpanKind.INTERNAL) as otel_span:
            with test_library.dd_start_span(name="dd_span", parent_id=otel_span.span_id) as dd_span:
                dd_current_span = test_library.dd_current_span()
                otel_context = otel_span.span_context()

                assert dd_current_span.trace_id == otel_context.get("trace_id")
                assert dd_current_span.span_id == dd_span.span_id

            otel_current_span = test_library.otel_current_span()
            assert otel_current_span.span_id == otel_span.span_id

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, otel_span.trace_id)
        assert len(trace) == 2

        root = find_root_span(trace)
        assert root is not None
        assert root.get("resource") == "otel_span"

        span = find_span(trace, dd_span.span_id)
        assert span is not None
        assert span.get("parent_id") == root.get("span_id")

    def test_set_update_remove_meta(self, test_agent, test_library):
        """- Test that meta is set/updated/removed across APIs"""
        with test_library, test_library.dd_start_span("dd_span") as dd_span:
            dd_span.set_meta("arg1", "val1")
            dd_span.set_meta("arg2", "val2")

            otel_span = test_library.otel_current_span()

            otel_span.set_attribute("arg3", "val3")
            otel_span.set_attribute("arg4", "val4")
            dd_span.set_meta("arg3", None)  # Remove the arg3/val3 pair (Created with the Otel API)
            otel_span.set_attribute("arg1", None)  # Remove the arg1/val1 pair (Created with the DD API)
            otel_span.set_attribute("arg2", "val3")  # Update the arg2/val2 pair (Created with the DD API)
            dd_span.set_meta("arg4", "val5")  # Update the arg4/val4 pair (Created with the Otel API)

            dd_span.finish()

            # The following calls should have no effect
            otel_span.set_attribute("arg5", "val5")  # Set a meta with the Otel API
            otel_span.set_attribute("arg2", "val4")  # Update the arg2/val2 pair (Created with the DD API)
            otel_span.set_attribute("arg2", None)  # Remove the arg2/val2 pair (Created with the DD API)

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, dd_span.trace_id)
        assert len(trace) == 1

        dd_span = find_root_span(trace)
        meta = dd_span["meta"]

        # Span-life changes
        assert "arg1" not in meta
        assert meta["arg2"] == "val3"
        assert "arg3" not in meta
        assert meta["arg4"] == "val5"

        # Afterlife changes
        assert "arg5" not in meta

    def test_set_update_remove_metric(self, test_agent, test_library):
        """- Test that metrics are set/updated/removed across APIs"""
        with test_library, test_library.dd_start_span("dd_span") as dd_span:
            dd_span.set_metric("m1", 1)  # Set a metric with the DD API
            dd_span.set_metric("m2", 2)

            otel_span = test_library.otel_current_span()

            otel_span.set_attribute("m3", 3)  # Set a metric with the Otel API
            otel_span.set_attribute("m4", 4)
            dd_span.set_metric("m3", None)  # Remove the m3/3 pair (Created with the Otel API)
            otel_span.set_attribute("m1", None)  # Remove the m1/1 pair (Created with the DD API)
            otel_span.set_attribute("m2", 3)  # Update the m2/2 pair (Created with the DD API)
            dd_span.set_metric("m4", 5)  # Update the m4/4 pair (Created with the Otel API)

            dd_span.finish()

            # The following calls should have no effect
            otel_span.set_attribute("m5", 5)  # Set a metric with the Otel API
            otel_span.set_attribute("m2", 4)  # Update the m2/2 pair (Created with the DD API)
            otel_span.set_attribute("m2", None)  # Remove the m2/2 pair (Created with the DD API)

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, dd_span.trace_id)
        assert len(trace) == 1

        dd_span = find_root_span(trace)
        metrics = dd_span["metrics"]

        # Span-life changes
        assert "m1" not in metrics
        assert metrics["m2"] == 3
        assert "m3" not in metrics
        assert metrics["m4"] == 5

        # Afterlife changes
        assert "m5" not in metrics

    def test_update_resource(self, test_agent, test_library):
        """- Test that the resource is updated across APIs"""
        with test_library, test_library.otel_start_span("my_resource") as otel_span:
            dd_span = test_library.dd_current_span()
            dd_span.set_resource("my_new_resource")
            dd_span.finish()
            assert not otel_span.is_recording()

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, otel_span.trace_id)
        span = find_span(trace, otel_span.span_id)
        assert span.get("resource") == "my_new_resource"

    def test_span_links_add(self, test_agent, test_library):
        """- Test that links can be added with the Datadog API on a span created with the OTel API"""
        with test_library:
            with test_library.dd_start_span("dd_root") as dd_span:
                pass

            with test_library.otel_start_span("otel_root") as otel_span:
                dd_current_span = test_library.dd_current_span()
                dd_current_span.add_link(parent_id=dd_span.span_id, attributes=TEST_ATTRIBUTES)

        traces = test_agent.wait_for_num_traces(2, sort_by_start=False)
        trace = find_trace(traces, otel_span.trace_id)
        assert len(trace) == 1

        root = find_root_span(trace)
        span_links = retrieve_span_links(root)
        assert len(span_links) == 1

    def test_concurrent_traces_in_order(self, test_agent, test_library):
        """- Basic concurrent traces and spans"""
        with (
            test_library,
            test_library.otel_start_span("otel_root", span_kind=SpanKind.SERVER) as otel_root,
            test_library.dd_start_span(name="dd_child", parent_id=otel_root.span_id) as dd_child,
            test_library.dd_start_span(name="dd_root", parent_id=0) as dd_root,
            test_library.otel_start_span(name="otel_child", parent_id=dd_root.span_id) as otel_child,
        ):
            pass

        traces = test_agent.wait_for_num_traces(2, sort_by_start=False)

        trace1 = find_trace(traces, otel_root.trace_id)
        assert len(trace1) == 2

        trace2 = find_trace(traces, dd_root.trace_id)
        assert len(trace2) == 2

        root1 = find_root_span(trace1)
        root2 = find_root_span(trace2)
        assert root1 is not None
        assert root2 is not None
        assert root1["resource"] == "otel_root"
        assert root2["name"] == "dd_root"

        child1 = find_span(trace1, dd_child.span_id)
        child2 = find_span(trace2, otel_child.span_id)
        assert child1["name"] == "dd_child"
        assert child2["resource"] == "otel_child"

        assert child1["parent_id"] == root1["span_id"]
        assert child2["parent_id"] == root2["span_id"]

        assert root1["trace_id"] == child1["trace_id"]
        assert root2["trace_id"] == child2["trace_id"]
        assert root1["trace_id"] != root2["trace_id"]

    def test_concurrent_traces_nested_otel_root(self, test_agent, test_library):
        """- Concurrent traces with nested start/end, with the first trace being opened with the OTel API"""
        with (
            test_library,
            test_library.otel_start_span(name="otel_root", span_kind=SpanKind.SERVER) as otel_root,
            test_library.dd_start_span(name="dd_root", parent_id=0) as dd_root,
        ):
            with test_library.otel_start_span(
                name="otel_child", parent_id=otel_root.span_id, span_kind=SpanKind.INTERNAL
            ) as otel_child:
                with test_library.dd_start_span(name="dd_child", parent_id=dd_root.span_id) as dd_child:
                    dd_current_span = test_library.dd_current_span()
                    assert dd_current_span.span_id == dd_child.span_id

                dd_current_span = test_library.dd_current_span()
                assert dd_current_span.span_id == dd_root.span_id
            dd_root.finish()

            dd_current_span = test_library.dd_current_span()
            assert dd_current_span.span_id == otel_root.span_id

        traces = test_agent.wait_for_num_traces(2, sort_by_start=False)

        trace1 = find_trace(traces, otel_root.trace_id)
        assert len(trace1) == 2

        trace2 = find_trace(traces, dd_root.trace_id)
        assert len(trace2) == 2

        root1 = find_root_span(trace1)
        root2 = find_root_span(trace2)
        assert root1 is not None
        assert root2 is not None
        assert root1["resource"] == "otel_root"
        assert root2["name"] == "dd_root"

        child1 = find_span(trace1, otel_child.span_id)
        child2 = find_span(trace2, dd_child.span_id)
        assert child1["resource"] == "otel_child"
        assert child2["name"] == "dd_child"

        assert child1["parent_id"] == root1["span_id"]
        assert child2["parent_id"] == root2["span_id"]

        assert root1["trace_id"] == child1["trace_id"]
        assert root2["trace_id"] == child2["trace_id"]
        assert root1["trace_id"] != root2["trace_id"]

    def test_concurrent_traces_nested_dd_root(self, test_agent, test_library):
        """- Concurrent traces with nested start/end, with the first trace being opened with the Datadog API"""
        with (
            test_library,
            test_library.dd_start_span(name="dd_root", parent_id=0) as dd_root,
            test_library.otel_start_span(name="otel_root", span_kind=SpanKind.SERVER) as otel_root,
        ):
            with test_library.otel_start_span(
                name="otel_child", parent_id=otel_root.span_id, span_kind=SpanKind.INTERNAL
            ) as otel_child:
                with test_library.dd_start_span(name="dd_child", parent_id=dd_root.span_id) as dd_child:
                    dd_current_span = test_library.dd_current_span()
                    assert dd_current_span.span_id == dd_child.span_id

                dd_current_span = test_library.dd_current_span()
                assert dd_current_span.span_id == dd_root.span_id
            dd_root.finish()

            dd_current_span = test_library.dd_current_span()
            assert dd_current_span.span_id == otel_root.span_id

        traces = test_agent.wait_for_num_traces(2, sort_by_start=False)

        trace1 = find_trace(traces, otel_root.trace_id)
        assert len(trace1) == 2

        trace2 = find_trace(traces, dd_root.trace_id)
        assert len(trace2) == 2

        root1 = find_root_span(trace1)
        root2 = find_root_span(trace2)
        assert root1 is not None
        assert root2 is not None
        assert root1["resource"] == "otel_root"
        assert root2["name"] == "dd_root"

        child1 = find_span(trace1, otel_child.span_id)
        child2 = find_span(trace2, dd_child.span_id)
        assert child1["resource"] == "otel_child"
        assert child2["name"] == "dd_child"

        assert child1["parent_id"] == root1["span_id"]
        assert child2["parent_id"] == root2["span_id"]

        assert root1["trace_id"] == child1["trace_id"]
        assert root2["trace_id"] == child2["trace_id"]
        assert root1["trace_id"] != root2["trace_id"]

    def test_distributed_headers_are_propagated_tracecontext(self, test_agent, test_library):
        """- Test that distributed tracecontext headers are propagated across APIs"""
        trace_id = "0000000000000000000000000000002a"  # 42
        parent_id = "0000000000000003"  # 3
        headers = [
            ("traceparent", f"00-{trace_id}-{parent_id}-01"),
            ("tracestate", "foo=1"),
        ]

        with test_library, test_library.dd_extract_headers_and_make_child_span("dd_span", headers):
            otel_span = test_library.otel_current_span()
            otel_context = otel_span.span_context()

            assert otel_context.get("trace_id") == trace_id
            assert "foo=1" in otel_context.get("trace_state")
            assert otel_context.get("trace_flags") == "01"

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        root = find_only_span(traces)
        assert root["parent_id"] == 3
        assert "foo" not in root["meta"]
        assert root["meta"]["_dd.p.dm"] == "-0"
        assert root["metrics"]["_sampling_priority_v1"] == 1

    def test_distributed_headers_are_propagated_datadog(self, test_agent, test_library):
        """- Test that distributed datadog headers are propagated across APIs"""

        headers = [
            ("x-datadog-trace-id", "123456789"),
            ("x-datadog-parent-id", "987654321"),
            ("x-datadog-sampling-priority", "-2"),
            ("x-datadog-tags", "_dd.p.foo=bar"),
            ("x-datadog-origin", "synthetics"),
        ]

        with test_library, test_library.dd_extract_headers_and_make_child_span("dd_span", headers):
            otel_span = test_library.otel_current_span()
            otel_context = otel_span.span_context()
            otel_trace_state = otel_context.get("trace_state")

            assert otel_context.get("trace_id") == "000000000000000000000000075bcd15"
            assert "o:synthetics" in otel_trace_state
            assert "s:-2" in otel_trace_state
            assert "t.foo:bar" in otel_trace_state
            assert otel_context.get("trace_flags") == "00"

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        root = find_only_span(traces)
        assert root["trace_id"] == 123456789
        assert root["parent_id"] == 987654321
        assert root["meta"]["_dd.p.foo"] == "bar"
        assert root["meta"]["_dd.origin"] == "synthetics"
        assert root["metrics"]["_sampling_priority_v1"] == -2

    def test_set_attribute_from_otel(self, test_agent, test_library: APMLibrary):
        """- Test that attributes can be set on a Datadog span using the OTel API"""
        with test_library, test_library.dd_start_span("dd_span") as dd_span:
            otel_span = test_library.otel_current_span()

            assert otel_span is not None

            otel_span.set_attribute("int", 1)
            otel_span.set_attribute("float", 1.0)
            otel_span.set_attribute("bool", value=True)
            otel_span.set_attribute("str", "string")
            otel_span.set_attribute("none", None)
            # Note: OTel's arrays MUST be homogeneous
            otel_span.set_attribute("str_array", ["a", "b", "c"])
            otel_span.set_attribute("nested_str_array", [["a", "b"], ["c", "d"]])
            otel_span.set_attribute("int_array", [1, 2, 3])

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, dd_span.trace_id)
        assert len(trace) == 1

        root = find_root_span(trace)
        assert root is not None
        assert root["metrics"]["int"] == 1
        assert root["metrics"]["float"] == 1.0
        assert root["meta"]["bool"] == "true"
        assert root["meta"]["str"] == "string"
        assert "none" not in root["meta"]
        assert root["meta"]["str_array.0"] == "a"
        assert root["meta"]["str_array.1"] == "b"
        assert root["meta"]["str_array.2"] == "c"
        assert root["meta"]["nested_str_array.0.0"] == "a"
        assert root["meta"]["nested_str_array.0.1"] == "b"
        assert root["meta"]["nested_str_array.1.0"] == "c"
        assert root["meta"]["nested_str_array.1.1"] == "d"
        assert root["metrics"]["int_array.0"] == 1
        assert root["metrics"]["int_array.1"] == 2
        assert root["metrics"]["int_array.2"] == 3

    def test_set_attribute_from_datadog(self, test_agent, test_library: APMLibrary):
        """- Test that attributes can be set on an OTel span using the Datadog API"""
        with test_library, test_library.otel_start_span(name="otel_span") as otel_span:
            dd_span = test_library.dd_current_span()

            assert dd_span is not None

            dd_span.set_metric("int", 1)
            dd_span.set_metric("float", 1.0)
            dd_span.set_meta("bool", val=True)
            dd_span.set_meta("str", "string")
            dd_span.set_meta("none", None)
            # Note: OTel's arrays MUST be homogeneous
            dd_span.set_meta("str_array", ["a", "b", "c"])
            dd_span.set_meta("nested_str_array", [["a", "b"], ["c", "d"]])
            dd_span.set_metric("int_array", [1, 2, 3])

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, otel_span.span_id)
        assert len(trace) == 1

        root = find_root_span(trace)
        assert root is not None
        assert root["metrics"]["int"] == 1
        assert root["metrics"]["float"] == 1.0
        assert root["meta"]["bool"] == "true"
        assert root["meta"]["str"] == "string"
        assert "none" not in root["meta"]
        assert root["meta"]["str_array.0"] == "a"
        assert root["meta"]["str_array.1"] == "b"
        assert root["meta"]["str_array.2"] == "c"
        assert root["meta"]["nested_str_array.0.0"] == "a"
        assert root["meta"]["nested_str_array.0.1"] == "b"
        assert root["meta"]["nested_str_array.1.0"] == "c"
        assert root["meta"]["nested_str_array.1.1"] == "d"
        assert root["metrics"]["int_array.0"] == 1
        assert root["metrics"]["int_array.1"] == 2
        assert root["metrics"]["int_array.2"] == 3
