import time

import pytest

from typing import Union
from utils.parametric._library_client import Link
from utils.parametric.spec.otel_trace import OTEL_UNSET_CODE, OTEL_ERROR_CODE, OTEL_OK_CODE
from utils.parametric.spec.otel_trace import OtelSpan, otel_span
from utils.parametric.spec.otel_trace import SK_PRODUCER, SK_INTERNAL, SK_SERVER, SK_CLIENT, SK_CONSUMER
from utils.parametric.spec.trace import find_span
from utils.parametric.spec.trace import find_trace_by_root
from utils.parametric.spec.trace import retrieve_span_links
from utils.parametric.spec.tracecontext import TRACECONTEXT_FLAGS_SET
from utils.parametric.test_agent import get_span
from utils import bug, missing_feature, irrelevant, context, scenarios

# this global mark applies to all tests in this file.
#   DD_TRACE_OTEL_ENABLED=true is required in some tracers (.NET, Python?)
#   CORECLR_ENABLE_PROFILING=1 is required in .NET to enable auto-instrumentation
pytestmark = pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_OTEL_ENABLED": "true", "CORECLR_ENABLE_PROFILING": "1"}],
)


@scenarios.parametric
class Test_Otel_Span_Methods:
    @missing_feature(context.library <= "java@1.23.0", reason="Implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="New operation name mapping not yet implemented")
    @missing_feature(context.library <= "dotnet@2.41.0", reason="Implemented in 2.42.0")
    @missing_feature(context.library == "python", reason="New operation name mapping not yet implemented")
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
        assert root_span["name"] == "producer"
        assert root_span["resource"] == "operation"
        assert root_span["meta"]["start_attr_key"] == "start_attr_val"
        assert root_span["duration"] == duration * 1_000  # OTEL expects microseconds but we convert it to ns internally

    @missing_feature(context.library <= "java@1.23.0", reason="Implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="New operation name mapping not yet implemented")
    @missing_feature(context.library <= "dotnet@2.41.0", reason="Implemented in 2.42.0")
    @missing_feature(context.library == "python", reason="New operation name mapping not yet implemented")
    def test_otel_set_service_name(self, test_agent, test_library):
        """
            - Update the service name on a span
        """
        with test_library:
            with test_library.otel_start_span("parent_span", span_kind=SK_INTERNAL) as parent:
                parent.set_attributes({"service.name": "new_service"})
                parent.end_span()

        root_span = get_span(test_agent)
        assert root_span["name"] == "internal"
        assert root_span["resource"] == "parent_span"
        assert root_span["service"] == "new_service"

    @irrelevant(
        context.library == "java",
        reason="Old array encoding was removed in 1.22.0 and new span naming introduced in 1.24.0: no version elligible for this test.",
    )
    @irrelevant(context.library >= "golang@v1.59.0.dev0", reason="New span naming introduced in v1.59.0")
    @irrelevant(context.library == "ruby", reason="Old array encoding no longer supported")
    @irrelevant(context.library == "php", reason="Old array encoding no longer supported")
    @missing_feature(context.library == "nodejs", reason="New operation name mapping not yet implemented")
    @missing_feature(context.library <= "dotnet@2.41.0", reason="Implemented in 2.42.0")
    @missing_feature(context.library == "python", reason="New operation name mapping not yet implemented")
    def test_otel_set_attributes_different_types_legacy(self, test_agent, test_library):
        """
            - Set attributes of multiple types for an otel span
            This tests legacy behavior. The new behavior is tested in
            test_otel_set_attributes_different_types_with_array_encoding
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
        trace = find_trace_by_root(traces, otel_span(name="operation"))
        assert len(trace) == 1

        root_span = get_span(test_agent)

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
    @missing_feature(
        context.library == "dotnet", reason="New operation name mapping & array encoding not yet implemented"
    )
    @missing_feature(
        context.library == "python", reason="New operation name mapping & array encoding not yet implemented"
    )
    def test_otel_set_attributes_different_types_with_array_encoding(self, test_agent, test_library):
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
        trace = find_trace_by_root(traces, otel_span(name="operation"))
        assert len(trace) == 1

        root_span = get_span(test_agent)

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

    @missing_feature(context.library <= "java@1.23.0", reason="Implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="New operation name mapping not yet implemented")
    @missing_feature(
        context.library == "dotnet",
        reason=".NET's native implementation does not change IsAllDataRequested to false after ending a span. OpenTelemetry follows this as well for IsRecording.",
    )
    @missing_feature(context.library == "python", reason="New operation name mapping not yet implemented")
    def test_otel_span_finished_end_options(self, test_agent, test_library):
        """
        Test functionality of ending a span with end options.
        After finishing the span, finishing the span with different end options has no effect
        """
        start_time: int = 12345
        duration: int = 6789
        with test_library:
            with test_library.otel_start_span(name="operation", span_kind=SK_INTERNAL, timestamp=start_time) as s:
                assert s.is_recording()
                s.end_span(timestamp=start_time + duration)
                assert not s.is_recording()
                s.end_span(timestamp=start_time + duration * 2)

        s = get_span(test_agent)
        assert s.get("name") == "internal"
        assert s.get("resource") == "operation"
        assert s.get("start") == start_time * 1_000  # OTEL expects microseconds but we convert it to ns internally
        assert s.get("duration") == duration * 1_000

    @missing_feature(context.library <= "java@1.23.0", reason="Implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="New operation name mapping not yet implemented")
    @missing_feature(context.library <= "dotnet@2.41.0", reason="Implemented in 2.42.0")
    @missing_feature(context.library == "python", reason="New operation name mapping not yet implemented")
    def test_otel_span_end(self, test_agent, test_library):
        """
        Test functionality of ending a span. After ending:
            - operations on that span become noop
            - child spans are still running and can be ended later
            - still possible to start child spans from parent context
        """
        with test_library:
            with test_library.otel_start_span(name="parent", span_kind=SK_PRODUCER) as parent:
                parent.end_span()
                # setting attributes after finish has no effect
                parent.set_name("new_name")
                parent.set_attributes({"after_finish": "true"})  # should have no affect
                with test_library.otel_start_span(
                    name="child", span_kind=SK_CONSUMER, parent_id=parent.span_id
                ) as child:
                    child.end_span()

        trace = find_trace_by_root(test_agent.wait_for_num_traces(1), otel_span(name="parent"))
        assert len(trace) == 2

        parent_span = find_span(trace, otel_span(name="parent"))
        assert parent_span["name"] == "producer"
        assert parent_span["resource"] == "parent"
        assert parent_span["meta"].get("after_finish") is None

        child = find_span(trace, otel_span(name="child"))
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
        """
            This test verifies that setting the status of a span
            behaves accordingly to the Otel API spec
            (https://opentelemetry.io/docs/reference/specification/trace/api/#set-status)
            By checking the following:
            1. attempts to set the value of `Unset` are ignored
            2. description must only be used with `Error` value

        """
        with test_library:
            with test_library.otel_start_span(name="error_span", span_kind=SK_INTERNAL) as s:
                s.set_status(OTEL_ERROR_CODE, "error_desc")
                s.set_status(OTEL_UNSET_CODE, "unset_desc")
                s.end_span()
        s = get_span(test_agent)
        assert s.get("meta").get("error.message") == "error_desc"
        assert s.get("name") == "internal"
        assert s.get("resource") == "error_span"

    @missing_feature(context.library <= "java@1.23.0", reason="Implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="New operation name mapping not yet implemented")
    @missing_feature(
        context.library == "dotnet",
        reason=".NET's native implementation and OpenTelemetry implementation do not enforce this and allow the status to be changed.",
    )
    @missing_feature(
        context.library == "python",
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
            with test_library.otel_start_span(name="ok_span", span_kind=SK_INTERNAL) as span:
                span.set_status(OTEL_OK_CODE, "ok_desc")
                span.set_status(OTEL_ERROR_CODE, "error_desc")
                span.end_span()

        span = get_span(test_agent)
        assert span.get("meta").get("error.message") is None
        assert span.get("name") == "internal"
        assert span.get("resource") == "ok_span"

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
                    if (
                        isinstance(span.span_id, str)
                        and len(span.span_id) == 16
                        and all(c in "0123456789abcdef" for c in span.span_id)
                    ):
                        # Some languages e.g. PHP return a hexadecimal span id
                        assert context.get("span_id") == span.span_id
                    else:
                        # Some languages e.g. Nodejs using express need to return as a string value
                        # due to 64-bit integers being too large.
                        assert context.get("span_id") == "{:016x}".format(int(span.span_id))
                    assert context.get("trace_flags") == "01"

    @missing_feature(context.library <= "java@1.23.0", reason="Implemented in 1.24.0")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library <= "dotnet@2.41.0", reason="Implemented in 2.42.0")
    @missing_feature(context.library == "python", reason="Not implemented")
    def test_otel_set_attributes_separately(self, test_agent, test_library):
        """
            This test verifies that setting attributes separately
            behaves accordingly to the naming conventions
        """
        with test_library:
            with test_library.otel_start_span(name="operation", span_kind=SK_CLIENT) as span:
                span.set_attributes({"messaging.system": "Kafka"})
                span.set_attributes({"messaging.operation": "Receive"})
                span.end_span()

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace_by_root(traces, otel_span(name="operation"))
        assert len(trace) == 1

        span = get_span(test_agent)
        assert span["name"] == "kafka.receive"
        assert span["resource"] == "operation"

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library < "java@1.26.0", reason="Implemented in 1.26.0")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    def test_otel_span_started_with_link_from_another_span(self, test_agent, test_library):
        """Test adding a span link created from another span.
        This tests the functionality of "create a direct link between two spans
        given two valid span (or SpanContext) objects" as specified in the RFC.
        """
        with test_library:
            with test_library.otel_start_span("root") as parent:
                parent.end_span()
                with test_library.otel_start_span(
                    "child",
                    parent_id=parent.span_id,
                    links=[Link(parent_id=parent.span_id, attributes={"foo": "bar", "array": ["a", "b", "c"]})],
                ) as child:
                    child.end_span()

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace_by_root(traces, otel_span(name="root"))
        assert len(trace) == 2

        root = find_span(trace, otel_span(name="root"))
        child = find_span(trace, otel_span(name="child"))
        assert child.get("parent_id") == root.get("span_id")

        span_links = retrieve_span_links(child)
        assert span_links is not None
        assert len(span_links) == 1

        link = span_links[0]
        assert link.get("span_id") == root.get("span_id")
        assert link.get("trace_id") == root.get("trace_id")
        root_tid = root["meta"].get("_dd.p.tid") or "0" if "meta" in root else "0"
        assert (link.get("trace_id_high") or 0) == int(root_tid, 16)
        assert link["attributes"].get("foo") == "bar"
        assert link["attributes"].get("array.0") == "a"
        assert link["attributes"].get("array.1") == "b"
        assert link["attributes"].get("array.2") == "c"

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library < "java@1.26.0", reason="Implemented in 1.26.0")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    def test_otel_span_started_with_link_from_datadog_headers(self, test_agent, test_library):
        """Properly inject datadog distributed tracing information into span links.
        """
        with test_library:
            with test_library.otel_start_span(
                "root",
                links=[
                    Link(
                        http_headers=[
                            ["x-datadog-trace-id", "1234567890"],
                            ["x-datadog-parent-id", "9876543210"],
                            ["x-datadog-sampling-priority", "2"],
                            ["x-datadog-origin", "synthetics"],
                            ["x-datadog-tags", "_dd.p.dm=-4,_dd.p.tid=0000000000000010"],
                        ],
                        attributes={"foo": "bar"},
                    )
                ],
            ) as span:
                span.end_span()

        span = get_span(test_agent)
        span_links = retrieve_span_links(span)
        assert span_links is not None
        assert len(span_links) == 1

        link = span_links[0]
        assert link.get("span_id") == 9876543210
        assert link.get("trace_id") == 1234567890
        assert link.get("trace_id_high") == 16

        # Tracestate is not required, but if it is present, it must be valid
        if link.get("tracestate"):
            tracestateArr = link["tracestate"].split(",")
            assert len(tracestateArr) == 1 and tracestateArr[0].startswith("dd=")
            tracestateDD = tracestateArr[0][3:].split(";")
            assert "o:synthetics" in tracestateDD
            assert "s:2" in tracestateDD
            assert "t.dm:-4" in tracestateDD
            # Sampled flag should be set to match the existing tracestate
            assert link.get("flags") == 1 | TRACECONTEXT_FLAGS_SET

        assert len(link.get("attributes")) == 1
        assert link["attributes"].get("foo") == "bar"

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library < "java@1.28.0", reason="Implemented in 1.28.0")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    def test_otel_span_started_with_link_from_w3c_headers(self, test_agent, test_library):
        """Properly inject w3c distributed tracing information into span links.
        This mostly tests that the injected tracestate and flags are accurate.
        """
        with test_library:
            with test_library.otel_start_span(
                "root",
                links=[
                    Link(
                        http_headers=[
                            ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                            ["tracestate", "foo=1,dd=t.dm:-4;s:2,bar=baz"],
                        ]
                    )
                ],
            ) as span:
                span.end_span()

        span = get_span(test_agent)
        span_links = retrieve_span_links(span)
        assert span_links is not None
        assert len(span_links) == 1

        link = span_links[0]
        assert link.get("span_id") == 1311768467284833366
        assert link.get("trace_id") == 8687463697196027922
        assert link.get("trace_id_high") == 1311768467284833366

        assert link.get("tracestate") is not None
        tracestateArr = link["tracestate"].split(",")
        assert len(tracestateArr) == 3
        dd_num = 0 if tracestateArr[0].startswith("dd=") else 1
        other_num = 0 if dd_num == 1 else 1
        assert tracestateArr[other_num] == "foo=1"
        assert tracestateArr[2] == "bar=baz"
        tracestateDD = tracestateArr[dd_num][3:].split(";")
        assert len(tracestateDD) == 2
        assert "s:2" in tracestateDD
        assert "t.dm:-4" in tracestateDD

        assert link.get("flags") == 1 | TRACECONTEXT_FLAGS_SET
        assert link.get("attributes") is None

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library < "java@1.26.0", reason="Implemented in 1.26.0")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    def test_otel_span_started_with_link_from_other_spans(self, test_agent, test_library):
        """Test adding a span link from a span to another span.
        """
        with test_library:
            with test_library.otel_start_span("root") as parent:
                parent.end_span()
                with test_library.otel_start_span("first", parent_id=parent.span_id) as first:
                    first.end_span()
                with test_library.otel_start_span(
                    "second",
                    parent_id=parent.span_id,
                    links=[
                        Link(parent_id=parent.span_id),
                        Link(parent_id=first.span_id, attributes={"bools": [True, False], "nested": [1, 2]}),
                    ],
                ) as second:
                    second.end_span()

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace_by_root(traces, otel_span(name="root"))
        assert len(trace) == 3

        root = find_span(trace, otel_span(name="root"))
        root_tid = root["meta"].get("_dd.p.tid") or "0" if "meta" in root else "0"

        first = find_span(trace, otel_span(name="first"))
        second = find_span(trace, otel_span(name="second"))
        assert second.get("parent_id") == root.get("span_id")

        span_links = retrieve_span_links(second)
        assert span_links is not None
        assert len(span_links) == 2

        link = span_links[0]
        assert link.get("span_id") == root.get("span_id")
        assert link.get("trace_id") == root.get("trace_id")
        assert link.get("trace_id_high") == int(root_tid, 16)
        assert link.get("attributes") is None
        # Tracestate is not required, but if it is present, it must contain the linked span's tracestate
        if link.get("tracestate"):
            assert link.get("tracestate") == "dd=s:1;t.dm:-0"

        link = span_links[1]
        assert link.get("span_id") == first.get("span_id")
        assert link.get("trace_id") == first.get("trace_id")
        assert link.get("trace_id_high") == int(root_tid, 16)
        assert len(link.get("attributes")) == 4
        assert link["attributes"].get("bools.0") == "true"
        assert link["attributes"].get("bools.1") == "false"
        assert link["attributes"].get("nested.0") == "1"
        assert link["attributes"].get("nested.1") == "2"
        if link.get("tracestate"):
            assert link.get("tracestate") == "dd=s:1;t.dm:-0"

    @missing_feature(context.library < "java@1.24.1", reason="Implemented in 1.24.1")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library <= "dotnet@2.41.0", reason="Implemented in 2.42.0")
    @missing_feature(context.library == "python", reason="Not implemented")
    @pytest.mark.parametrize(
        "expected_operation_name,span_kind,attributes",
        [
            ("http.server.request", SK_SERVER, {"http.request.method": "GET"}),
            ("http.client.request", SK_CLIENT, {"http.request.method": "GET"}),
            ("redis.query", SK_CLIENT, {"db.system": "Redis"}),
            ("kafka.receive", SK_CLIENT, {"messaging.system": "Kafka", "messaging.operation": "Receive"}),
            ("kafka.receive", SK_SERVER, {"messaging.system": "Kafka", "messaging.operation": "Receive"}),
            ("kafka.receive", SK_PRODUCER, {"messaging.system": "Kafka", "messaging.operation": "Receive"}),
            ("kafka.receive", SK_CONSUMER, {"messaging.system": "Kafka", "messaging.operation": "Receive"}),
            ("aws.s3.request", SK_CLIENT, {"rpc.system": "aws-api", "rpc.service": "S3"}),
            ("aws.client.request", SK_CLIENT, {"rpc.system": "aws-api"}),
            ("grpc.client.request", SK_CLIENT, {"rpc.system": "GRPC"}),
            ("grpc.server.request", SK_SERVER, {"rpc.system": "GRPC"}),
            ("aws.my-function.invoke", SK_CLIENT, {"faas.invoked_provider": "aws", "faas.invoked_name": "My-Function"}),
            ("datasource.invoke", SK_SERVER, {"faas.trigger": "Datasource"}),
            ("graphql.server.request", SK_SERVER, {"graphql.operation.type": "query"}),
            ("amqp.server.request", SK_SERVER, {"network.protocol.name": "Amqp"}),
            ("server.request", SK_SERVER, None),
            ("amqp.client.request", SK_CLIENT, {"network.protocol.name": "Amqp"}),
            ("client.request", SK_CLIENT, None),
            ("internal", SK_INTERNAL, None),
            ("consumer", SK_CONSUMER, None),
            ("producer", SK_PRODUCER, None),
            ("internal", None, None),
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

    @missing_feature(context.library < "java@1.25.0", reason="Implemented in 1.25.0")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library <= "dotnet@2.41.0", reason="Implemented in 2.42.0")
    @missing_feature(context.library == "python", reason="Not implemented")
    def test_otel_span_reserved_attributes_overrides(self, test_agent, test_library):
        """
            Tests that the reserved attributes will override expected values
        """
        with test_library:
            with test_library.otel_start_span("otel_span_name", span_kind=SK_SERVER) as span:
                span.set_attributes({"http.request.method": "GET"})
                span.set_attributes({"resource.name": "new.name"})
                span.set_attributes({"operation.name": "overriden.name"})
                span.set_attributes({"service.name": "new.service.name"})
                span.set_attributes({"span.type": "new.span.type"})
                span.set_attributes({"analytics.event": "true"})
                span.end_span()
        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace_by_root(traces, otel_span(name="new.name"))
        assert len(trace) == 1

        span = get_span(test_agent)
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

    @missing_feature(context.library < "java@1.25.0", reason="Implemented in 1.25.0")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library <= "php@0.95.0", reason="Implemented in 0.96.0")
    @missing_feature(context.library == "python", reason="Not implemented")
    @pytest.mark.parametrize(
        "analytics_event_value,expected_metric_value",
        [("true", 1), ("TRUE", 1), ("True", 1), ("false", 0), ("False", 0), ("FALSE", 0), (True, 1), (False, 0),],
    )
    def test_otel_span_basic_reserved_attributes_overrides_analytics_event(
        self, analytics_event_value: Union[bool, str], expected_metric_value: Union[int, None], test_agent, test_library
    ):
        """
            Tests the analytics.event reserved attribute override with basic inputs
        """
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
    @pytest.mark.parametrize(
        "analytics_event_value,expected_metric_value", [("something-else", None), ("fAlse", None), ("trUe", None),],
    )
    def test_otel_span_strict_reserved_attributes_overrides_analytics_event(
        self, analytics_event_value: Union[bool, str], expected_metric_value: Union[int, None], test_agent, test_library
    ):
        """
            Tests that the analytics.event reserved attribute override doesn't set the _dd1.sr.eausr metric
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
    @pytest.mark.parametrize(
        "analytics_event_value,expected_metric_value", [("t", 1), ("T", 1), ("f", 0), ("F", 0), ("1", 1), ("0", 0),],
    )
    def test_otel_span_extended_reserved_attributes_overrides_analytics_event(
        self, analytics_event_value: Union[bool, str], expected_metric_value: Union[int, None], test_agent, test_library
    ):
        """
            Tests that the analytics.event reserved attribute override accepts Go's strconv.ParseBool additional values
        """
        run_otel_span_reserved_attributes_overrides_analytics_event(
            analytics_event_value=analytics_event_value,
            expected_metric_value=expected_metric_value,
            test_library=test_library,
            test_agent=test_agent,
        )


def run_operation_name_test(expected_operation_name: str, span_kind: int, attributes: dict, test_library, test_agent):
    with test_library:
        with test_library.otel_start_span("otel_span_name", span_kind=span_kind, attributes=attributes) as span:
            span.end_span()
    traces = test_agent.wait_for_num_traces(1)
    trace = find_trace_by_root(traces, otel_span(name="otel_span_name"))
    assert len(trace) == 1

    span = get_span(test_agent)
    assert span["name"] == expected_operation_name
    assert span["resource"] == "otel_span_name"


def run_otel_span_reserved_attributes_overrides_analytics_event(
    analytics_event_value: Union[bool, str], expected_metric_value: Union[int, None], test_agent, test_library
):
    with test_library:
        with test_library.otel_start_span("operation", span_kind=SK_SERVER) as span:
            span.set_attributes({"analytics.event": analytics_event_value})
            span.end_span()
    traces = test_agent.wait_for_num_traces(1)
    trace = find_trace_by_root(traces, otel_span(name="operation"))
    assert len(trace) == 1

    span = get_span(test_agent)
    if expected_metric_value is not None:
        assert span["metrics"].get("_dd1.sr.eausr") == expected_metric_value
    else:
        assert "_dd1.sr.eausr" not in span["metrics"]
    assert "analytics.event" not in span["meta"]
