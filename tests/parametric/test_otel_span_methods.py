import time

import json
import pytest

from utils.parametric._library_client import Link
from opentelemetry.trace import StatusCode
from opentelemetry.trace import SpanKind
from utils.parametric.spec.trace import find_span, retrieve_span_events
from utils.parametric.spec.trace import find_trace
from utils.parametric.spec.trace import retrieve_span_links
from utils.parametric.spec.trace import find_first_span_in_trace_payload
from utils import bug, features, missing_feature, irrelevant, context, scenarios

# this global mark applies to all tests in this file.
#   DD_TRACE_OTEL_ENABLED=true is required in some tracers (.NET, Python?)
#   CORECLR_ENABLE_PROFILING=1 is required in .NET to enable auto-instrumentation
pytestmark = pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_OTEL_ENABLED": "true", "CORECLR_ENABLE_PROFILING": "1"}]
)


@scenarios.parametric
@features.open_tracing_api
class Test_Otel_Span_Methods:
    @missing_feature(context.library <= "java@1.23.0", reason="Implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="New operation name mapping not yet implemented")
    @missing_feature(context.library <= "dotnet@2.41.0", reason="Implemented in 2.42.0")
    @missing_feature(context.library == "python", reason="New operation name mapping not yet implemented")
    def test_otel_start_span(self, test_agent, test_library):
        """- Start/end a span with start and end options"""

        with test_library:
            duration: int = 6789
            start_time: int = 12345
            with test_library.otel_start_span(
                "operation",
                span_kind=SpanKind.PRODUCER,
                timestamp=start_time,
                attributes={"start_attr_key": "start_attr_val"},
            ) as parent:
                parent.end_span(timestamp=start_time + duration)

        traces = test_agent.wait_for_num_traces(num=1)
        trace = find_trace(traces, parent.trace_id)
        root_span = find_span(trace, parent.span_id)
        assert root_span["name"] == "producer"
        assert root_span["resource"] == "operation"
        assert root_span["meta"]["start_attr_key"] == "start_attr_val"
        assert root_span["duration"] == duration * 1_000  # OTEL expects microseconds but we convert it to ns internally

    @missing_feature(context.library <= "java@1.23.0", reason="Implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="New operation name mapping not yet implemented")
    @missing_feature(context.library <= "dotnet@2.41.0", reason="Implemented in 2.42.0")
    @missing_feature(context.library == "python", reason="New operation name mapping not yet implemented")
    def test_otel_set_service_name(self, test_agent, test_library):
        """- Update the service name on a span"""
        with test_library, test_library.otel_start_span("parent_span", span_kind=SpanKind.INTERNAL) as parent:
            parent.set_attributes({"service.name": "new_service"})

        traces = test_agent.wait_for_num_traces(num=1)
        trace = find_trace(traces, parent.trace_id)
        root_span = find_span(trace, parent.span_id)
        assert root_span["name"] == "internal"
        assert root_span["resource"] == "parent_span"
        assert root_span["service"] == "new_service"

    @missing_feature(context.library < "python@2.9.0", reason="Implemented in 2.9.0")
    @missing_feature(context.library < "golang@1.65.0", reason="Implemented in 1.65.0")
    @missing_feature(context.library < "ruby@2.0.0", reason="Implemented in 2.0.0")
    @missing_feature(context.library < "php@1.1.0", reason="Implemented in 1.1.0")
    @missing_feature(context.library < "nodejs@5.16.0", reason="Implemented in 5.16.0")
    @missing_feature(context.library < "nodejs@4.40.0", reason="Implemented in 5.40.0")
    @missing_feature(context.library < "java@1.35.0", reason="Implemented in 1.35.0")
    @missing_feature(context.library < "dotnet@2.53.0", reason="Implemented in 2.53.0")
    def test_otel_set_attribute_remapping_httpresponsestatuscode(self, test_agent, test_library):
        """- May 2024 update to OTel API RFC requires implementations to remap
        OTEL Span attribute 'http.response.status_code' to DD Span tag 'http.status_code'.
        This solves an issue with trace metrics when using the OTel API.
        """
        with test_library, test_library.otel_start_span("operation") as span:
            span.set_attributes({"http.response.status_code": 200})

        traces = test_agent.wait_for_num_traces(num=1)
        trace = find_trace(traces, span.trace_id)
        test_span = find_span(trace, span.span_id)

        assert "http.response.status_code" not in test_span["meta"]
        assert test_span["meta"]["http.status_code"] == "200"

    @missing_feature(context.library < "python@2.9.0", reason="Implemented in 2.9.0")
    @missing_feature(context.library < "ruby@2.0.0", reason="Implemented in 2.0.0")
    @missing_feature(context.library < "nodejs@5.16.0", reason="Implemented in 5.16.0")
    @missing_feature(context.library < "nodejs@4.40.0", reason="Implemented in 5.40.0")
    @missing_feature(context.library < "java@1.35.0", reason="Implemented in 1.35.0")
    @missing_feature(context.library < "php@1.1.0", reason="Implemented in 1.2.0")
    @irrelevant(context.library == "golang", reason="Does not support automatic status code remapping to meta")
    @irrelevant(context.library == "dotnet", reason="Does not support automatic status code remapping to meta")
    def test_otel_set_attribute_remapping_httpstatuscode(self, test_agent, test_library):
        """- May 2024 update to OTel API RFC requires implementations to remap
        OTEL Span attribute 'http.response.status_code' to DD Span tag 'http.status_code'.
        This test ensures that the original OTEL Span attribute 'http.status_code'
        is also set as DD Span tag 'http.status_code'
        """
        with test_library, test_library.otel_start_span("operation") as span:
            span.set_attributes({"http.status_code": 200})

        traces = test_agent.wait_for_num_traces(num=1)
        trace = find_trace(traces, span.trace_id)
        test_span = find_span(trace, span.span_id)

        assert test_span["meta"]["http.status_code"] == "200"

    @irrelevant(
        context.library == "java",
        reason="Old array encoding was removed in 1.22.0 and new span naming introduced in 1.24.0: no version elligible for this test.",
    )
    @irrelevant(context.library >= "golang@v1.59.0.dev0", reason="New span naming introduced in v1.59.0")
    @irrelevant(context.library == "ruby", reason="Old array encoding no longer supported")
    @irrelevant(context.library == "php", reason="Old array encoding no longer supported")
    @missing_feature(context.library > "dotnet@2.52.0", reason="Old array encoding no longer supported")
    @missing_feature(context.library == "nodejs", reason="New operation name mapping not yet implemented")
    @missing_feature(context.library == "python", reason="New operation name mapping not yet implemented")
    @missing_feature(context.library == "rust", reason="Old array encoding not supported")
    def test_otel_set_attributes_different_types_legacy(self, test_agent, test_library):
        """- Set attributes of multiple types for an otel span
        This tests legacy behavior. The new behavior is tested in
        test_otel_set_attributes_different_types_with_array_encoding
        """
        start_time = int(time.time())
        with (
            test_library,
            test_library.otel_start_span("operation", span_kind=SpanKind.PRODUCER, timestamp=start_time) as span,
        ):
            span.set_attributes({"str_val": "val"})
            span.set_attributes({"str_val_empty": ""})
            span.set_attributes({"bool_val": True})
            span.set_attributes({"int_val": 1})
            span.set_attributes({"int_val_zero": 0})
            span.set_attributes({"double_val": 4.2})
            span.set_attributes({"array_val_str": ["val1", "val2"]})
            span.set_attributes({"array_val_int": [10, 20]})
            span.set_attributes({"array_val_bool": [True, False]})
            span.set_attributes({"array_val_double": [10.1, 20.2]})
            span.set_attributes({"d_str_val": "bye", "d_bool_val": False, "d_int_val": 2, "d_double_val": 3.14})

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.trace_id)
        assert len(trace) == 1

        root_span = find_span(trace, span.span_id)

        assert root_span["name"] == "producer"
        assert root_span["resource"] == "operation"

        assert root_span["meta"]["str_val"] == "val"
        assert root_span["meta"]["str_val_empty"] == ""
        if root_span["meta"]["language"] == "go":
            # in line with the standard Datadog tracing library tags
            assert root_span["meta"]["bool_val"] == "true"
            assert root_span["meta"]["d_bool_val"] == "false"
            assert root_span["meta"]["array_val_bool"] == "[true false]"
            assert root_span["meta"]["array_val_str"] == "[val1 val2]"
            assert root_span["meta"]["array_val_int"] == "[10 20]"
            assert root_span["meta"]["array_val_double"] == "[10.1 20.2]"
        elif root_span["meta"]["language"] == "jvm":
            assert root_span["meta"]["bool_val"] == "true"
            assert root_span["meta"]["array_val_bool"] == "[true, false]"
            assert root_span["meta"]["array_val_str"] == "[val1, val2]"
            assert root_span["meta"]["d_bool_val"] == "false"
            assert root_span["meta"]["array_val_int"] == "[10, 20]"
            assert root_span["meta"]["array_val_double"] == "[10.1, 20.2]"
        elif root_span["meta"]["language"] == "dotnet":
            assert root_span["meta"]["bool_val"] == "true"
            assert root_span["meta"]["array_val_bool"] == "[true,false]"
            assert root_span["meta"]["array_val_str"] == '["val1","val2"]'
            assert root_span["meta"]["d_bool_val"] == "false"
            assert root_span["meta"]["array_val_int"] == "[10,20]"
            assert root_span["meta"]["array_val_double"] == "[10.1,20.2]"
        else:
            assert root_span["meta"]["bool_val"] == "True"
            assert root_span["meta"]["array_val_bool"] == "[True, False]"
            assert root_span["meta"]["array_val_str"] == "['val1', 'val2']"
            assert root_span["meta"]["d_bool_val"] == "False"
            assert root_span["meta"]["array_val_int"] == "[10, 20]"
            assert root_span["meta"]["array_val_double"] == "[10.1, 20.2]"
        assert root_span["metrics"]["int_val"] == 1
        assert root_span["metrics"]["int_val_zero"] == 0
        assert root_span["metrics"]["double_val"] == 4.2
        assert root_span["meta"]["d_str_val"] == "bye"
        assert root_span["metrics"]["d_int_val"] == 2
        assert root_span["metrics"]["d_double_val"] == 3.14

    @missing_feature(
        context.library < "java@1.24.0",
        reason="New array encoding implemented in 1.22.0 and new operation name mapping in 1.24.0",
    )
    @missing_feature(
        context.library < "golang@1.59.0",
        reason="New naming breaks old tests, so only run old tests on previous versions.",
    )
    @missing_feature(
        context.library == "nodejs", reason="New operation name mapping & array encoding not yet implemented"
    )
    @missing_feature(context.library <= "dotnet@2.52.0", reason="Implemented in 2.53.0")
    @missing_feature(
        context.library == "python", reason="New operation name mapping & array encoding not yet implemented"
    )
    def test_otel_set_attributes_different_types_with_array_encoding(self, test_agent, test_library):
        """- Set attributes of multiple types for an otel span"""
        start_time = int(time.time())
        with (
            test_library,
            test_library.otel_start_span("operation", span_kind=SpanKind.PRODUCER, timestamp=start_time) as span,
        ):
            span.set_attributes({"str_val": "val"})
            span.set_attributes({"str_val_empty": ""})
            span.set_attributes({"bool_val": True})
            span.set_attributes({"int_val": 1})
            span.set_attributes({"int_val_zero": 0})
            span.set_attributes({"double_val": 4.2})
            span.set_attributes({"array_val_str": ["val1", "val2"]})
            span.set_attributes({"array_val_int": [10, 20]})
            span.set_attributes({"array_val_bool": [True, False]})
            span.set_attributes({"array_val_double": [10.1, 20.2]})
            span.set_attributes({"d_str_val": "bye", "d_bool_val": False, "d_int_val": 2, "d_double_val": 3.14})

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.trace_id)
        assert len(trace) == 1

        root_span = find_span(trace, span.span_id)

        assert root_span["name"] == "producer"
        assert root_span["resource"] == "operation"

        assert root_span["meta"]["str_val"] == "val"
        assert root_span["meta"]["str_val_empty"] == ""
        assert root_span["meta"]["bool_val"] == "true"
        assert root_span["metrics"]["int_val"] == 1
        assert root_span["metrics"]["int_val_zero"] == 0
        assert root_span["metrics"]["double_val"] == 4.2

        assert root_span["meta"]["array_val_str.0"] == "val1"
        assert root_span["meta"]["array_val_str.1"] == "val2"

        assert root_span["metrics"]["array_val_int.0"] == 10
        assert root_span["metrics"]["array_val_int.1"] == 20

        assert root_span["meta"]["array_val_bool.0"] == "true"
        assert root_span["meta"]["array_val_bool.1"] == "false"

        assert root_span["metrics"]["array_val_double.0"] == 10.1
        assert root_span["metrics"]["array_val_double.1"] == 20.2

        assert root_span["meta"]["d_str_val"] == "bye"
        assert root_span["meta"]["d_bool_val"] == "false"
        assert root_span["metrics"]["d_int_val"] == 2
        assert root_span["metrics"]["d_double_val"] == 3.14

    @missing_feature(
        context.library == "dotnet",
        reason=".NET's native implementation does not change IsAllDataRequested to false after ending a span. OpenTelemetry follows this as well for IsRecording.",
    )
    def test_otel_span_is_recording(self, test_agent, test_library):
        """Test functionality of ending a span.
        - before ending - span.is_recording() is true
        - after ending - span.is_recording() is false
        """
        with test_library:
            # start parent
            with test_library.otel_start_span(name="parent", end_on_exit=True) as parent:
                assert parent.is_recording()
            assert not parent.is_recording()

    @missing_feature(context.library <= "java@1.23.0", reason="Implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="New operation name mapping not yet implemented")
    @missing_feature(
        context.library == "dotnet",
        reason=".NET's native implementation does not change IsAllDataRequested to false after ending a span. OpenTelemetry follows this as well for IsRecording.",
    )
    @missing_feature(context.library == "python", reason="New operation name mapping not yet implemented")
    def test_otel_span_finished_end_options(self, test_agent, test_library):
        """Test functionality of ending a span with end options.
        After finishing the span, finishing the span with different end options has no effect
        """
        start_time: int = 12345
        duration: int = 6789
        with (
            test_library,
            test_library.otel_start_span(name="operation", span_kind=SpanKind.INTERNAL, timestamp=start_time) as span,
        ):
            assert span.is_recording()
            span.end_span(timestamp=start_time + duration)
            assert not span.is_recording()
            span.end_span(timestamp=start_time + duration * 2)

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.trace_id)
        s = find_span(trace, span.span_id)
        assert s.get("name") == "internal"
        assert s.get("resource") == "operation"
        assert s.get("start") == start_time * 1_000  # OTEL expects microseconds but we convert it to ns internally
        assert s.get("duration") == duration * 1_000

    @missing_feature(context.library <= "java@1.23.0", reason="Implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="New operation name mapping not yet implemented")
    @missing_feature(context.library <= "dotnet@2.41.0", reason="Implemented in 2.42.0")
    @missing_feature(context.library == "python", reason="New operation name mapping not yet implemented")
    def test_otel_span_end(self, test_agent, test_library):
        """Test functionality of ending a span. After ending:
        - operations on that span become noop
        - child spans are still running and can be ended later
        - still possible to start child spans from parent context
        """
        with (
            test_library,
            test_library.otel_start_span(name="parent", span_kind=SpanKind.PRODUCER, end_on_exit=False) as parent,
        ):
            parent.end_span()
            # setting attributes after finish has no effect
            parent.set_name("new_name")
            parent.set_attributes({"after_finish": "true"})  # should have no affect
            with test_library.otel_start_span(
                name="child", span_kind=SpanKind.CONSUMER, parent_id=parent.span_id
            ) as child:
                pass

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, parent.trace_id)
        assert len(trace) == 2

        parent_span = find_span(trace, parent.span_id)
        assert parent_span["name"] == "producer"
        assert parent_span["resource"] == "parent"
        assert parent_span["meta"].get("after_finish") is None

        child = find_span(trace, child.span_id)
        assert child["name"] == "consumer"
        assert child["resource"] == "child"
        assert child["parent_id"] == parent_span["span_id"]

    @missing_feature(context.library <= "java@1.23.0", reason="Implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="New operation name mapping not yet implemented")
    @missing_feature(
        context.library == "dotnet",
        reason=".NET's native implementation unsets the error message. OpenTelemetry also unsets the error message.",
    )
    @missing_feature(context.library == "python", reason="New operation name mapping not yet implemented")
    def test_otel_set_span_status_error(self, test_agent, test_library):
        """This test verifies that setting the status of a span
        behaves accordingly to the Otel API spec
        (https://opentelemetry.io/docs/reference/specification/trace/api/#set-status)
        By checking the following:
        1. attempts to set the value of `Unset` are ignored
        2. description must only be used with `Error` value

        """
        with test_library, test_library.otel_start_span(name="error_span", span_kind=SpanKind.INTERNAL) as s:
            s.set_status(StatusCode.ERROR, "error_desc")
            s.set_status(StatusCode.UNSET, "unset_desc")

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, s.trace_id)
        s = find_span(trace, s.span_id)
        assert s.get("meta").get("error.message") == "error_desc"
        assert s.get("name") == "internal"
        assert s.get("resource") == "error_span"

    @missing_feature(context.library <= "java@1.23.0", reason="Implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="New operation name mapping not yet implemented")
    @missing_feature(
        context.library == "python",
        reason="Default state of otel spans is OK, updating the status from OK to ERROR is supported",
    )
    def test_otel_set_span_status_ok(self, test_agent, test_library):
        """This test verifies that setting the status of a span
        behaves accordingly to the Otel API spec
        (https://opentelemetry.io/docs/reference/specification/trace/api/#set-status)
        By checking the following:
        1. attempts to set the value of `Unset` are ignored
        3. setting the status to `Ok` is final and will override any
            prior or future status values
        """
        with test_library, test_library.otel_start_span(name="ok_span", span_kind=SpanKind.INTERNAL) as span:
            span.set_status(StatusCode.OK, "ok_desc")
            span.set_status(StatusCode.ERROR, "error_desc")

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.trace_id)
        span = find_span(trace, span.span_id)
        assert span.get("meta").get("error.message") is None
        assert span.get("name") == "internal"
        assert span.get("resource") == "ok_span"

    @bug(context.library < "ruby@2.2.0", reason="APMRP-360")
    @missing_feature(context.library == "rust", reason="APMSP-2059")
    def test_otel_get_span_context(self, test_agent, test_library):
        """This test verifies retrieving the span context of a span
        accordingly to the Otel API spec
        (https://opentelemetry.io/docs/reference/specification/trace/api/#get-context)
        """
        with test_library, test_library.otel_start_span(name="op1", end_on_exit=False) as parent:
            parent.end_span()
            with test_library.otel_start_span(name="op2", parent_id=parent.span_id, end_on_exit=False) as span:
                span.end_span()
                context = span.span_context()
                assert context.get("trace_id") == parent.span_context().get("trace_id")
                if (
                    isinstance(span.span_id, str)
                    and len(span.span_id) == 16
                    and all(c in "0123456789abcdef" for c in span.span_id)
                ):
                    # Some languages e.g. PHP return a hexadecimal span id
                    assert context.get("span_id") == span.span_id
                else:
                    # Some languages e.g. Node.js using express need to return as a string value
                    # due to 64-bit integers being too large.
                    assert context.get("span_id") == f"{int(span.span_id):016x}"
                assert context.get("trace_flags") == "01"

        # compare the values of the span context with the values of the trace sent to the agent
        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, span.trace_id)
        op2 = find_span(trace, span.span_id)
        assert op2["resource"] == "op2"
        assert op2["span_id"] == int(context["span_id"], 16)
        first_span = find_first_span_in_trace_payload(trace)
        op2_tidhex = first_span["meta"].get("_dd.p.tid", "") + "{:016x}".format(first_span["trace_id"])
        assert int(op2_tidhex, 16) == int(context["trace_id"], 16)

    @missing_feature(context.library <= "java@1.23.0", reason="Implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library <= "dotnet@2.41.0", reason="Implemented in 2.42.0")
    @missing_feature(context.library == "python", reason="Not implemented")
    def test_otel_set_attributes_separately(self, test_agent, test_library):
        """This test verifies that setting attributes separately
        behaves accordingly to the naming conventions
        """
        with test_library, test_library.otel_start_span(name="operation", span_kind=SpanKind.CLIENT) as span:
            span.set_attributes({"messaging.system": "Kafka"})
            span.set_attributes({"messaging.operation": "Receive"})

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.trace_id)
        assert len(trace) == 1

        span = find_span(trace, span.span_id)
        assert span["name"] == "kafka.receive"
        assert span["resource"] == "operation"

    @missing_feature(context.library < "dotnet@2.53.0", reason="Will be released in 2.53.0")
    @missing_feature(context.library < "java@1.26.0", reason="Implemented in 1.26.0")
    @missing_feature(context.library < "nodejs@5.3.0", reason="Implemented in 3.48.0, 4.27.0, and 5.3.0")
    @missing_feature(context.library < "golang@1.61.0", reason="Implemented in 1.61.0")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library < "php@0.97.0", reason="Implemented in 0.97.0")
    @missing_feature(context.library == "rust", reason="APMSP-2059")
    def test_otel_span_started_with_link_from_another_span(self, test_agent, test_library):
        """Test adding a span link created from another span.
        This tests the functionality of "create a direct link between two spans
        given two valid span (or SpanContext) objects" as specified in the RFC.
        """
        with test_library, test_library.otel_start_span("root", end_on_exit=False) as parent:
            parent.end_span()
            with test_library.otel_start_span(
                "child",
                parent_id=parent.span_id,
                links=[Link(parent_id=parent.span_id, attributes={"foo": "bar", "array": ["a", "b", "c"]})],
            ) as child:
                pass

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, parent.trace_id)
        assert len(trace) == 2

        root = find_span(trace, parent.span_id)
        child = find_span(trace, child.span_id)
        assert child.get("parent_id") == root.get("span_id")

        span_links = retrieve_span_links(child)
        assert span_links is not None
        assert len(span_links) == 1

        link = span_links[0]
        assert link.get("span_id") == root.get("span_id")
        assert link.get("trace_id") == root.get("trace_id")
        if "trace_id_high" in link:
            root_tid = root["meta"].get("_dd.p.tid", "0")
            assert link.get("trace_id_high") == int(root_tid, 16)

    @missing_feature(context.library < "dotnet@2.53.0", reason="Will be released in 2.53.0")
    @missing_feature(context.library < "java@1.26.0", reason="Implemented in 1.26.0")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.3.0", reason="Implemented in 3.48.0, 4.27.0, and 5.3.0")
    @missing_feature(context.library < "ruby@2.0.0", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented, does not break out arrays into dot notation")
    def test_otel_span_link_attribute_handling(self, test_agent, test_library):
        """Test that span links implementations correctly handle attributes according to spec."""
        with test_library:
            with test_library.otel_start_span("span1") as s1:
                s1.end_span()

            with test_library.otel_start_span(
                "root",
                links=[
                    Link(
                        parent_id=s1.span_id,
                        attributes={"foo": "bar", "array": ["a", "b", "c"], "bools": [True, False], "nested": [1, 2]},
                    )
                ],
            ) as s2:
                pass

        traces = test_agent.wait_for_num_traces(2)
        trace = find_trace(traces, s2.trace_id)
        span = find_span(trace, s2.span_id)
        span_links = retrieve_span_links(span)
        assert span_links is not None
        assert len(span_links) == 1

        link = span_links[0]

        assert len(link.get("attributes")) == 8
        assert link["attributes"].get("foo") == "bar"
        assert link["attributes"].get("nested.0") == "1"
        assert link["attributes"].get("nested.1") == "2"
        assert link["attributes"].get("array.0") == "a"
        assert link["attributes"].get("array.1") == "b"
        assert link["attributes"].get("array.2") == "c"
        assert link["attributes"].get("bools.0").casefold() == "true"
        assert link["attributes"].get("bools.1").casefold() == "false"

    @missing_feature(context.library < "dotnet@2.53.0", reason="Will be released in 2.53.0")
    @missing_feature(context.library < "java@1.26.0", reason="Implemented in 1.26.0")
    @missing_feature(context.library < "golang@1.61.0", reason="Implemented in 1.61.0")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library < "ruby@2.0.0", reason="Not implemented")
    @bug(context.library == "ruby", reason="APMAPI-917")
    @missing_feature(context.library < "php@0.97.0", reason="Implemented in 0.97.0")
    @missing_feature(context.library == "rust", reason="APMSP-2059")
    def test_otel_span_started_with_link_from_other_spans(self, test_agent, test_library):
        """Test adding a span link from a span to another span."""
        with test_library, test_library.otel_start_span("root", end_on_exit=False) as parent:
            parent.end_span()
            with test_library.otel_start_span("first", parent_id=parent.span_id) as first:
                pass

            with test_library.otel_start_span(
                "second",
                parent_id=parent.span_id,
                links=[
                    Link(parent_id=parent.span_id),
                    Link(parent_id=first.span_id, attributes={"bools": [True, False], "nested": [1, 2]}),
                ],
            ) as second:
                pass

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, parent.trace_id)
        assert len(trace) == 3

        root = find_span(trace, parent.span_id)
        root_tid = root["meta"].get("_dd.p.tid") or "0" if "meta" in root else "0"

        first = find_span(trace, first.span_id)
        second = find_span(trace, second.span_id)
        assert second.get("parent_id") == root.get("span_id")

        span_links = retrieve_span_links(second)
        assert span_links is not None
        assert len(span_links) == 2

        link = span_links[0]
        assert link.get("span_id") == root.get("span_id")
        assert link.get("trace_id") == root.get("trace_id")
        assert link.get("trace_id_high") == int(root_tid, 16)
        assert link.get("attributes") is None or len(link.get("attributes")) == 0
        # Tracestate is not required, but if it is present, it must contain the linked span's tracestate
        assert link.get("tracestate") is None or "dd=" in link.get("tracestate")

        link = span_links[1]
        assert link.get("span_id") == first.get("span_id")
        assert link.get("trace_id") == first.get("trace_id")
        assert link.get("trace_id_high") == int(root_tid, 16)
        assert link.get("tracestate") is None or "dd=" in link.get("tracestate")

    @missing_feature(context.library < "java@1.24.1", reason="Implemented in 1.24.1")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library <= "dotnet@2.41.0", reason="Implemented in 2.42.0")
    @missing_feature(context.library == "python", reason="Not implemented")
    @pytest.mark.parametrize(
        ("expected_operation_name", "span_kind", "attributes"),
        [
            ("http.server.request", SpanKind.SERVER, {"http.request.method": "GET"}),
            ("http.client.request", SpanKind.CLIENT, {"http.request.method": "GET"}),
            ("redis.query", SpanKind.CLIENT, {"db.system": "Redis"}),
            ("kafka.receive", SpanKind.CLIENT, {"messaging.system": "Kafka", "messaging.operation": "Receive"}),
            ("kafka.receive", SpanKind.SERVER, {"messaging.system": "Kafka", "messaging.operation": "Receive"}),
            ("kafka.receive", SpanKind.PRODUCER, {"messaging.system": "Kafka", "messaging.operation": "Receive"}),
            ("kafka.receive", SpanKind.CONSUMER, {"messaging.system": "Kafka", "messaging.operation": "Receive"}),
            ("aws.s3.request", SpanKind.CLIENT, {"rpc.system": "aws-api", "rpc.service": "S3"}),
            ("aws.client.request", SpanKind.CLIENT, {"rpc.system": "aws-api"}),
            ("grpc.client.request", SpanKind.CLIENT, {"rpc.system": "GRPC"}),
            ("grpc.server.request", SpanKind.SERVER, {"rpc.system": "GRPC"}),
            (
                "aws.my-function.invoke",
                SpanKind.CLIENT,
                {"faas.invoked_provider": "aws", "faas.invoked_name": "My-Function"},
            ),
            ("datasource.invoke", SpanKind.SERVER, {"faas.trigger": "Datasource"}),
            ("graphql.server.request", SpanKind.SERVER, {"graphql.operation.type": "query"}),
            ("amqp.server.request", SpanKind.SERVER, {"network.protocol.name": "Amqp"}),
            ("server.request", SpanKind.SERVER, None),
            ("amqp.client.request", SpanKind.CLIENT, {"network.protocol.name": "Amqp"}),
            ("client.request", SpanKind.CLIENT, None),
            ("internal", SpanKind.INTERNAL, None),
            ("consumer", SpanKind.CONSUMER, None),
            ("producer", SpanKind.PRODUCER, None),
        ],
    )
    def test_otel_span_operation_name(
        self, expected_operation_name: str, span_kind: int, attributes: dict, test_agent, test_library
    ):
        run_operation_name_test(
            expected_operation_name=expected_operation_name,
            span_kind=span_kind,
            attributes=attributes,
            test_library=test_library,
            test_agent=test_agent,
        )

    @missing_feature(context.library < "java@1.25.1", reason="Implemented in 1.25.1")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library <= "dotnet@2.41.0", reason="Implemented in 2.42.0")
    @missing_feature(context.library == "python", reason="Not implemented")
    def test_otel_span_reserved_attributes_overrides(self, test_agent, test_library):
        """Tests that the reserved attributes will override expected values"""
        with test_library, test_library.otel_start_span("otel_span_name", span_kind=SpanKind.SERVER) as span:
            span.set_attributes({"http.request.method": "GET"})
            span.set_attributes({"resource.name": "new.name"})
            span.set_attributes({"operation.name": "overriden.name"})
            span.set_attributes({"service.name": "new.service.name"})
            span.set_attributes({"span.type": "new.span.type"})
            span.set_attributes({"analytics.event": "true"})

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.trace_id)
        assert len(trace) == 1

        span = find_span(trace, span.span_id)
        assert span["name"] == "overriden.name"
        assert span["meta"]["span.kind"] == "server"
        assert span["resource"] == "new.name"
        assert span["service"] == "new.service.name"
        assert span["type"] == "new.span.type"
        assert span["metrics"].get("_dd1.sr.eausr") == 1

        assert "resource.name" not in span["meta"]
        assert "operation.name" not in span["meta"]
        assert "service.name" not in span["meta"]
        assert "span.type" not in span["meta"]
        assert "analytics.event" not in span["meta"]

    @missing_feature(context.library < "java@1.25.1", reason="Implemented in 1.25.1")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library <= "php@0.95.0", reason="Implemented in 0.96.0")
    @missing_feature(context.library == "python", reason="Not implemented")
    @pytest.mark.parametrize(
        ("analytics_event_value", "expected_metric_value"),
        [("true", 1), ("TRUE", 1), ("True", 1), ("false", 0), ("False", 0), ("FALSE", 0), (True, 1), (False, 0)],
    )
    def test_otel_span_basic_reserved_attributes_overrides_analytics_event(
        self, analytics_event_value: bool | str, expected_metric_value: int | None, test_agent, test_library
    ):
        """Tests the analytics.event reserved attribute override with basic inputs"""
        run_otel_span_reserved_attributes_overrides_analytics_event(
            analytics_event_value=analytics_event_value,
            expected_metric_value=expected_metric_value,
            test_library=test_library,
            test_agent=test_agent,
        )

    @irrelevant(
        context.library == "java",
        reason="Java tracer decided to always set _dd1.sr.eausr: 1 for truthy analytics.event inputs, else 0",
    )
    @irrelevant(
        context.library == "golang",
        reason="Go tracer decided to always set _dd1.sr.eausr: 1 for truthy analytics.event inputs, else 0",
    )
    @irrelevant(
        context.library == "ruby",
        reason="Ruby tracer decided to always set _dd1.sr.eausr: 1 for truthy analytics.event inputs, else 0",
    )
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library <= "php@0.95.0", reason="Implemented in 0.96.0")
    @missing_feature(context.library == "python", reason="Not implemented")
    @missing_feature(context.library == "python_http", reason="Not implemented")
    @missing_feature(context.library == "rust", reason="Not implemented")
    @pytest.mark.parametrize(
        ("analytics_event_value", "expected_metric_value"), [("something-else", None), ("fAlse", None), ("trUe", None)]
    )
    def test_otel_span_strict_reserved_attributes_overrides_analytics_event(
        self, analytics_event_value: bool | str, expected_metric_value: int | None, test_agent, test_library
    ):
        """Tests that the analytics.event reserved attribute override doesn't set the _dd1.sr.eausr metric
        for inputs that aren't accepted by strconv.ParseBool
        """
        run_otel_span_reserved_attributes_overrides_analytics_event(
            analytics_event_value=analytics_event_value,
            expected_metric_value=expected_metric_value,
            test_library=test_library,
            test_agent=test_agent,
        )

    @irrelevant(context.library == "java", reason="Choose to not implement Go parsing logic")
    @irrelevant(context.library == "ruby", reason="Choose to not implement Go parsing logic")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library <= "php@0.95.0", reason="Implemented in 0.96.0")
    @missing_feature(context.library == "python", reason="Not implemented")
    @missing_feature(context.library == "python_http", reason="Not implemented")
    @missing_feature(context.library == "rust", reason="Not implemented")
    @pytest.mark.parametrize(
        ("analytics_event_value", "expected_metric_value"), [("t", 1), ("T", 1), ("f", 0), ("F", 0), ("1", 1), ("0", 0)]
    )
    def test_otel_span_extended_reserved_attributes_overrides_analytics_event(
        self, analytics_event_value: bool | str, expected_metric_value: int | None, test_agent, test_library
    ):
        """Tests that the analytics.event reserved attribute override accepts Go's strconv.ParseBool additional values"""
        run_otel_span_reserved_attributes_overrides_analytics_event(
            analytics_event_value=analytics_event_value,
            expected_metric_value=expected_metric_value,
            test_library=test_library,
            test_agent=test_agent,
        )

    @missing_feature(
        context.library in ("dotnet", "golang", "ruby"),
        reason="Newer agents/testagents enabled native span event serialization by default",
    )
    @missing_feature(context.library < "php@1.3.0", reason="Not implemented")
    @missing_feature(context.library < "java@1.40.0", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.17.0", reason="Implemented in v5.17.0 & v4.41.0")
    @missing_feature(context.library < "python@2.9.0", reason="Not implemented")
    def test_otel_add_event_meta_serialization(self, test_agent, test_library):
        """Tests the Span.AddEvent API and its serialization into the meta tag 'events'"""
        # Since timestamps may not be standardized across languages, use microseconds as the input
        # and nanoseconds as the output (this is the format expected in the OTLP trace protocol)
        event2_timestamp_microseconds = int(time.time_ns() / 1000)
        event2_timestamp_ns = event2_timestamp_microseconds * 1000
        with test_library, test_library.otel_start_span("operation") as span:
            span.add_event(name="first_event")
            span.add_event(
                name="second_event", timestamp=event2_timestamp_microseconds, attributes={"string_val": "value"}
            )
            span.add_event(
                name="third_event",
                timestamp=1,
                attributes={"int_val": 1, "string_val": "2", "int_array": [3, 4], "string_array": ["5", "6"]},
            )

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.trace_id)
        root_span = find_span(trace, span.span_id)

        events = retrieve_span_events(root_span)
        assert len(events) == 3

        event1 = events[0]
        assert event1.get("name") == "first_event"
        assert "attributes" not in event1

        event2 = events[1]
        assert event2.get("name") == "second_event"
        assert abs(event2.get("time_unix_nano") - event2_timestamp_ns) < 100000  # reduce the precision tested
        assert event2["attributes"].get("string_val") == "value"

        event3 = events[2]
        assert event3.get("name") == "third_event"
        assert 999 <= event3.get("time_unix_nano") <= 1001  # reduce the precision tested
        assert event3["attributes"].get("int_val") == 1
        assert event3["attributes"].get("string_val") == "2"

        v04_v07_events = "span_events" in root_span

        if v04_v07_events:
            assert event3["attributes"].get("int_array.0") == 3
            assert event3["attributes"].get("int_array.1") == 4
            assert event3["attributes"].get("string_array.0") == "5"
            assert event3["attributes"].get("string_array.1") == "6"
        else:    
            assert event3["attributes"].get("int_array")[0] == 3
            assert event3["attributes"].get("int_array")[1] == 4
            assert event3["attributes"].get("string_array")[0] == "5"
            assert event3["attributes"].get("string_array")[1] == "6"

    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library < "php@1.3.0", reason="Not implemented")
    @missing_feature(context.library < "java@1.40.0", reason="Not implemented")
    @missing_feature(context.library < "ruby@2.3.0", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.17.0", reason="Implemented in v5.17.0 & v4.41.0")
    @missing_feature(context.library < "python@2.9.0", reason="Not implemented")
    def test_otel_record_exception_does_not_set_error(self, test_agent, test_library):
        """Tests the Span.RecordException API (requires Span.AddEvent API support)
        and its serialization into the Datadog error tags and the 'events' tag
        """
        with test_library, test_library.otel_start_span("operation") as span:
            span.record_exception(message="woof", attributes={"exception.stacktrace": "stacktrace string"})

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.trace_id)
        root_span = find_span(trace, span.span_id)
        assert "error" not in root_span or root_span["error"] == 0

    @missing_feature(
        context.library in ("dotnet", "golang", "ruby"),
        reason="Newer agents/testagents enabled native span event serialization by default",
    )
    @missing_feature(context.library < "php@1.3.0", reason="Not implemented")
    @missing_feature(context.library < "java@1.40.0", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.17.0", reason="Implemented in v5.17.0 & v4.41.0")
    @missing_feature(context.library < "python@2.9.0", reason="Not implemented")
    def test_otel_record_exception_meta_serialization(self, test_agent, test_library):
        """Tests the Span.RecordException API (requires Span.AddEvent API support)
        and its serialization into the Datadog error tags and the 'events' tag
        """
        with test_library, test_library.otel_start_span("operation") as span:
            span.set_status(StatusCode.ERROR, "error_desc")
            span.record_exception(
                message="woof1", attributes={"string_val": "value", "exception.stacktrace": "stacktrace1"}
            )
            span.add_event(name="non_exception_event", attributes={"exception.stacktrace": "non-error"})
            span.record_exception(message="woof3", attributes={"exception.message": "message override"})

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.trace_id)
        root_span = find_span(trace, span.span_id)
        assert "events" in root_span["meta"] or "span_events" in root_span

        events = retrieve_span_events(root_span)
        assert len(events) == 3
        event1 = events[0]
        assert (
            event1.get("name").lower() == "exception" or "error"
        )  # node uses error objects instead of exception objects
        assert event1.get("time_unix_nano") > 0

        event2 = events[1]
        assert event2.get("name") == "non_exception_event"
        assert event2.get("time_unix_nano") > event1.get("time_unix_nano")

        event3 = events[2]
        assert event3.get("name") == "exception" or "error"
        assert event3.get("time_unix_nano") > event2.get("time_unix_nano")

        assert root_span["error"] == 1
        assert "error.stack" in root_span["meta"]
        # For PHP we set only the error.stack tag on the meta to not interfere with the defined semantics of the PHP tracer
        # https://github.com/DataDog/dd-trace-php/pull/2754#discussion_r1704232289
        if context.library != "php":
            assert "error.type" in root_span["meta"]

    @missing_feature(context.library < "php@1.3.0", reason="Not implemented")
    @missing_feature(context.library < "java@1.40.0", reason="Not implemented")
    @missing_feature(context.library == "nodejs", reason="Otel Node.js API does not support attributes")
    @missing_feature(context.library < "python@2.9.0", reason="Not implemented")
    @missing_feature(
        context.library in ("dotnet", "golang", "ruby"),
        reason="Newer agents/testagents enabled native span event serialization by default",
    )
    def test_otel_record_exception_attributes_serialization(self, test_agent, test_library):
        """Tests the Span.RecordException API (requires Span.AddEvent API support)
        and its serialization into the Datadog error tags and the 'events' tag
        """
        with test_library, test_library.otel_start_span("operation") as span:
            span.set_status(StatusCode.ERROR, "error_desc")
            span.record_exception(
                message="woof1", attributes={"string_val": "value", "exception.stacktrace": "stacktrace1"}
            )
            span.add_event(name="non_exception_event", attributes={"exception.stacktrace": "non-error"})
            span.record_exception(message="woof3", attributes={"exception.message": "message override"})

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.trace_id)
        root_span = find_span(trace, span.span_id)
        assert "events" in root_span["meta"] or "span_events" in root_span

        events = retrieve_span_events(root_span)
        assert len(events) == 3
        event1 = events[0]
        assert event1["attributes"].get("string_val") == "value"
        assert event1["attributes"].get("exception.message") == "woof1"
        assert event1["attributes"].get("exception.stacktrace") == "stacktrace1"

        event2 = events[1]
        assert event2["attributes"].get("exception.stacktrace") == "non-error"
        
        event3 = events[2]
        assert event3["attributes"].get("exception.message") == "message override"
        
        # For PHP we set only the error.stack tag on the meta to not interfere with the defined semantics of the PHP tracer
        # https://github.com/DataDog/dd-trace-php/pull/2754#discussion_r1704232289
        if context.library != "php":
            error_message = root_span["meta"].get("error.message") or root_span["meta"].get("error.msg")
            assert error_message == "message override"

    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(
        context.library == "php", reason="Not supported: DD only sets error.stack to not break tracer semantics"
    )
    @missing_feature(context.library == "dotnet")
    @missing_feature(context.library < "java@1.40.0", reason="Not implemented")
    @missing_feature(context.library < "ruby@2.3.0", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.17.0", reason="Implemented in v5.17.0 & v4.41.0")
    @missing_feature(context.library < "python@2.9.0", reason="Not implemented")
    def test_otel_record_exception_sets_all_error_tracking_tags(self, test_agent, test_library):
        """Tests the Span.RecordException API (requires Span.AddEvent API support)
        and its serialization into the Datadog error tags and the 'events' tag
        """
        with test_library, test_library.otel_start_span("operation") as span:
            span.set_status(StatusCode.ERROR, "error_desc")
            span.record_exception(
                message="woof1", attributes={"string_val": "value", "exception.stacktrace": "stacktrace1"}
            )

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, span.trace_id)
        root_span = find_span(trace, span.span_id)

        assert root_span["error"] == 1
        assert "error.stack" in root_span["meta"]
        assert "error.message" in root_span["meta"]
        assert "error.type" in root_span["meta"]


def run_operation_name_test(expected_operation_name: str, span_kind: int, attributes: dict, test_library, test_agent):
    with (
        test_library,
        test_library.otel_start_span("otel_span_name", span_kind=span_kind, attributes=attributes) as span,
    ):
        pass

    traces = test_agent.wait_for_num_traces(1)
    trace = find_trace(traces, span.trace_id)
    assert len(trace) == 1

    span = find_span(trace, span.span_id)
    assert span["name"] == expected_operation_name
    assert span["resource"] == "otel_span_name"


def run_otel_span_reserved_attributes_overrides_analytics_event(
    analytics_event_value: bool | str, expected_metric_value: int | None, test_agent, test_library
):
    with test_library, test_library.otel_start_span("operation", span_kind=SpanKind.SERVER) as span:
        span.set_attributes({"analytics.event": analytics_event_value})

    traces = test_agent.wait_for_num_traces(1)
    trace = find_trace(traces, span.trace_id)
    assert len(trace) == 1

    span = find_span(trace, span.span_id)
    if expected_metric_value is not None:
        assert span["metrics"].get("_dd1.sr.eausr") == expected_metric_value
    else:
        assert "_dd1.sr.eausr" not in span["metrics"]
    assert "analytics.event" not in span["meta"]
