import time

import pytest

from utils.parametric.spec.otel_trace import OTEL_UNSET_CODE, OTEL_ERROR_CODE, OTEL_OK_CODE
from utils.parametric.spec.otel_trace import OtelSpan
from utils.parametric.spec.otel_trace import SK_PRODUCER
from utils.parametric.spec.trace import find_span
from utils.parametric.spec.trace import find_trace_by_root
from utils.parametric.test_agent import get_span
from utils import missing_feature, irrelevant, context, scenarios

# this global mark applies to all tests in this file.
#   DD_TRACE_OTEL_ENABLED=true is required in some tracers (.NET, Python?)
#   CORECLR_ENABLE_PROFILING=1 is required in .NET to enable auto-instrumentation
pytestmark = pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_OTEL_ENABLED": "true", "CORECLR_ENABLE_PROFILING": "1"}],
)


@scenarios.parametric
class Test_Otel_Span_Methods:
    @irrelevant(context.library == "cpp", reason="library does not implement OpenTelemetry")
    @missing_feature(context.library == "php", reason="Not implemented")
    def test_otel_start_span(self, test_agent, test_library):
        """
            - Start/end a span with start and end options
        """

        with test_library:
            duration: int = 6789
            start_time: int = 12345
            with test_library.otel_start_span(
                "operation",
                span_kind=SK_PRODUCER,
                timestamp=start_time,
                attributes={"start_attr_key": "start_attr_val"},
            ) as parent:
                parent.end_span(timestamp=start_time + duration)

        root_span = get_span(test_agent)
        assert root_span["name"] == "operation"
        assert root_span["resource"] == "operation"
        assert root_span["meta"]["start_attr_key"] == "start_attr_val"
        assert root_span["duration"] == duration * 1_000  # OTEL expects microseconds but we convert it to ns internally

    @irrelevant(context.library == "cpp", reason="library does not implement OpenTelemetry")
    @missing_feature(context.library == "php", reason="Not implemented")
    def test_otel_set_service_name(self, test_agent, test_library):
        """
            - Update the service name on a span
        """
        with test_library:
            with test_library.otel_start_span("parent_span") as parent:
                parent.set_attributes({"service.name": "new_service"})
                parent.end_span()

        root_span = get_span(test_agent)
        assert root_span["name"] == "parent_span"
        assert root_span["service"] == "new_service"

    @irrelevant(context.library == "cpp", reason="library does not implement OpenTelemetry")
    @missing_feature(context.library == "nodejs", reason="Empty string attribute value are not supported")
    @missing_feature(context.library == "php", reason="Not implemented")
    def test_otel_set_attributes_different_types(self, test_agent, test_library):
        """
            - Set attributes of multiple types for an otel span
        """
        start_time = int(time.time())
        with test_library:
            with test_library.otel_start_span("operation", span_kind=SK_PRODUCER, timestamp=start_time,) as span:
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
                span.end_span()
        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace_by_root(traces, OtelSpan(name="operation"))
        assert len(trace) == 1

        root_span = get_span(test_agent)

        assert root_span["name"] == "operation"
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
        elif root_span["meta"]["language"] == "ruby":
            assert root_span["meta"]["bool_val"] == "true"
            assert root_span["meta"]["array_val_bool"] == "[true, false]"
            assert root_span["meta"]["array_val_str"] == '["val1", "val2"]'

            assert root_span["meta"]["d_bool_val"] == "false"
            assert root_span["meta"]["array_val_int"] == "[10, 20]"
            assert root_span["meta"]["array_val_double"] == "[10.1, 20.2]"
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

    @irrelevant(context.library == "cpp", reason="library does not implement OpenTelemetry")
    @missing_feature(
        context.library == "dotnet",
        reason=".NET's native implementation does not change IsAllDataRequested to false after ending a span. OpenTelemetry follows this as well for IsRecording.",
    )
    @missing_feature(context.library == "php", reason="Not implemented")
    def test_otel_span_is_recording(self, test_agent, test_library):
        """
        Test functionality of ending a span.
            - before ending - span.is_recording() is true
            - after ending - span.is_recording() is false
        """
        with test_library:
            # start parent
            with test_library.otel_start_span(name="parent") as parent:
                assert parent.is_recording()
                parent.end_span()
                assert not parent.is_recording()

    @irrelevant(context.library == "cpp", reason="library does not implement OpenTelemetry")
    @missing_feature(
        context.library == "dotnet",
        reason=".NET's native implementation does not change IsAllDataRequested to false after ending a span. OpenTelemetry follows this as well for IsRecording.",
    )
    @missing_feature(context.library == "php", reason="Not implemented")
    def test_otel_span_finished_end_options(self, test_agent, test_library):
        """
        Test functionality of ending a span with end options.
        After finishing the span, finishing the span with different end options has no effect
        """
        start_time: int = 12345
        duration: int = 6789
        with test_library:
            with test_library.otel_start_span(name="operation", timestamp=start_time) as s:
                assert s.is_recording()
                s.end_span(timestamp=start_time + duration)
                assert not s.is_recording()
                s.end_span(timestamp=start_time + duration * 2)

        s = get_span(test_agent)
        assert s.get("name") == "operation"
        assert s.get("start") == start_time * 1_000  # OTEL expects microseconds but we convert it to ns internally
        assert s.get("duration") == duration * 1_000

    @irrelevant(context.library == "cpp", reason="library does not implement OpenTelemetry")
    @missing_feature(context.library == "php", reason="Not implemented")
    def test_otel_span_end(self, test_agent, test_library):
        """
        Test functionality of ending a span. After ending:
            - operations on that span become noop
            - child spans are still running and can be ended later
            - still possible to start child spans from parent context
        """
        with test_library:
            with test_library.otel_start_span(name="parent") as parent:
                parent.end_span()
                # setting attributes after finish has no effect
                parent.set_name("new_name")
                parent.set_attributes({"after_finish": "true"})  # should have no affect
                with test_library.otel_start_span(name="child", parent_id=parent.span_id) as child:
                    child.end_span()

        trace = find_trace_by_root(test_agent.wait_for_num_traces(1), OtelSpan(name="parent"))
        assert len(trace) == 2

        parent_span = find_span(trace, OtelSpan(name="parent"))
        assert parent_span["name"] == "parent"
        assert parent_span["meta"].get("after_finish") is None

        child = find_span(trace, OtelSpan(name="child"))
        assert child["name"] == "child"
        assert child["parent_id"] == parent_span["span_id"]

    @irrelevant(context.library == "cpp", reason="library does not implement OpenTelemetry")
    @missing_feature(
        context.library == "dotnet",
        reason=".NET's native implementation unsets the error message. OpenTelemetry also unsets the error message.",
    )
    @missing_feature(context.library == "php", reason="Not implemented")
    def test_otel_set_span_status_error(self, test_agent, test_library):
        """
            This test verifies that setting the status of a span
            behaves accordingly to the Otel API spec
            (https://opentelemetry.io/docs/reference/specification/trace/api/#set-status)
            By checking the following:
            1. attempts to set the value of `Unset` are ignored
            2. description must only be used with `Error` value

        """
        with test_library:
            with test_library.otel_start_span(name="error_span") as s:
                s.set_status(OTEL_ERROR_CODE, "error_desc")
                s.set_status(OTEL_UNSET_CODE, "unset_desc")
                s.end_span()
        s = get_span(test_agent)
        assert s.get("meta").get("error.message") == "error_desc"
        assert s.get("name") == "error_span"

    @irrelevant(context.library == "cpp", reason="library does not implement OpenTelemetry")
    @missing_feature(
        context.library == "dotnet",
        reason=".NET's native implementation and OpenTelemetry implementation do not enforce this and allow the status to be changed.",
    )
    @missing_feature(context.library == "php", reason="Not implemented")
    @missing_feature(
        context.library == "python",
        reason="Default state of otel spans is OK, updating the status from OK to ERROR is supported",
    )
    @missing_feature(
        context.library == "python_http",
        reason="Default state of otel spans is OK, updating the status from OK to ERROR is supported",
    )
    def test_otel_set_span_status_ok(self, test_agent, test_library):
        """
            This test verifies that setting the status of a span
            behaves accordingly to the Otel API spec
            (https://opentelemetry.io/docs/reference/specification/trace/api/#set-status)
            By checking the following:
            1. attempts to set the value of `Unset` are ignored
            3. setting the status to `Ok` is final and will override any
                prior or future status values
        """
        with test_library:
            with test_library.otel_start_span(name="ok_span") as span:
                span.set_status(OTEL_OK_CODE, "ok_desc")
                span.set_status(OTEL_ERROR_CODE, "error_desc")
                span.end_span()

        span = get_span(test_agent)
        assert span.get("meta").get("error.message") is None
        assert span.get("name") == "ok_span"

    @irrelevant(context.library == "cpp", reason="library does not implement OpenTelemetry")
    @missing_feature(context.library == "php", reason="Not implemented")
    def test_otel_get_span_context(self, test_agent, test_library):
        """
            This test verifies retrieving the span context of a span
            accordingly to the Otel API spec
            (https://opentelemetry.io/docs/reference/specification/trace/api/#get-context)
        """
        with test_library:
            with test_library.otel_start_span(name="operation") as parent:
                parent.end_span()
                with test_library.otel_start_span(name="operation", parent_id=parent.span_id) as span:
                    span.end_span()
                    context = span.span_context()
                    assert context.get("trace_id") == parent.span_context().get("trace_id")
                    assert context.get("span_id") == "{:016x}".format(span.span_id)
                    assert context.get("trace_flags") == "01"
