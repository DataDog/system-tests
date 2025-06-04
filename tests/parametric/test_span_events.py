import json
import pytest

from utils import scenarios, features, rfc, irrelevant, missing_feature, context
from utils.parametric.spec.trace import find_span, find_trace


@rfc("https://docs.google.com/document/d/1cVod_VI7Yruq8U9dfMRFJd7npDu-uBpste2IB04GyaQ")
@scenarios.parametric
@features.span_events
class Test_Span_Events:
    def _test_span_with_native_event(self, _library_env, test_agent, test_library):
        """Test adding a span event, with attributes, to an active span.
        Assumes native format where all values are serialized according to their original type.
        """
        time0 = 123450  # microseconds
        name0 = "event_name"
        attributes0 = {
            "string": "bar",
            "bool": True,
            "int": 1,
            "double": 2.3,
            "str_arr": ["a", "b", "c"],
            "bool_arr": [True, False],
            "int_arr": [5, 6],
            "double_arr": [1.1, 2.2],
        }

        time1 = 123451  # microseconds
        name1 = "other_event"
        attributes1 = {"bool": False, "int": 0, "double": 0.0}

        with test_library, test_library.otel_start_span("test") as s:
            s.add_event(name0, timestamp=time0, attributes=attributes0)
            s.add_event(name1, timestamp=time1, attributes=attributes1)

        traces = test_agent.wait_for_num_traces(1)

        trace = find_trace(traces, s.trace_id)
        assert len(trace) == 1
        span = find_span(trace, s.span_id)

        span_events = span["span_events"]

        assert len(span_events) == 2

        event = span_events[0]
        assert event["time_unix_nano"] == time0 * 1000  # microseconds to nanoseconds
        assert event["name"] == name0
        assert event["attributes"].get("string") == {"type": 0, "string_value": "bar"}
        assert event["attributes"].get("bool") == {"type": 1, "bool_value": True}
        assert event["attributes"].get("int") == {"type": 2, "int_value": 1}
        assert event["attributes"].get("double") == {"type": 3, "double_value": 2.3}

        assert event["attributes"].get("str_arr") == {
            "type": 4,
            "array_value": {
                "values": [
                    {"type": 0, "string_value": "a"},
                    {"type": 0, "string_value": "b"},
                    {"type": 0, "string_value": "c"},
                ]
            },
        }
        assert event["attributes"].get("bool_arr") == {
            "type": 4,
            "array_value": {"values": [{"type": 1, "bool_value": True}, {"type": 1, "bool_value": False}]},
        }
        assert event["attributes"].get("int_arr") == {
            "type": 4,
            "array_value": {"values": [{"type": 2, "int_value": 5}, {"type": 2, "int_value": 6}]},
        }
        assert event["attributes"].get("double_arr") == {
            "type": 4,
            "array_value": {"values": [{"type": 3, "double_value": 1.1}, {"type": 3, "double_value": 2.2}]},
        }

        event = span_events[1]
        assert event["time_unix_nano"] == time1 * 1000
        assert event["name"] == name1
        assert event["attributes"].get("bool") == {"type": 1, "bool_value": False}
        assert event["attributes"].get("int") == {"type": 2, "int_value": 0}
        assert isinstance(event["attributes"].get("int").get("int_value"), int)
        assert event["attributes"].get("double") == {"type": 3, "double_value": 0.0}
        assert isinstance(event["attributes"].get("double").get("double_value"), float)

    def _test_span_with_meta_event(self, _library_env, test_agent, test_library):
        """Test adding a span event, with attributes, to an active span.
        Assumes meta format where all values are strings.
        """
        time0 = 123450  # microseconds
        name0 = "event_name"
        attributes0 = {
            "string": "bar",
            "bool": "true",
            "int": "1",
            "double": "2.3",
            "str_arr": ["a", "b", "c"],
            "bool_arr": ["true", "false"],
            "int_arr": ["5", "6"],
            "double_arr": ["1.1", "2.2"],
        }

        time1 = 123451  # microseconds
        name1 = "other_event"
        attributes1 = {"bool": "false", "int": "0", "double": "0.0"}

        with test_library, test_library.otel_start_span("test") as s:
            s.add_event(name0, timestamp=time0, attributes=attributes0)
            s.add_event(name1, timestamp=time1, attributes=attributes1)

        traces = test_agent.wait_for_num_traces(1)

        trace = find_trace(traces, s.trace_id)
        assert len(trace) == 1
        span = find_span(trace, s.span_id)

        span_events = json.loads(span.get("meta", {}).get("events"))

        assert len(span_events) == 2

        event = span_events[0]
        assert event["time_unix_nano"] == time0 * 1000  # microseconds to nanoseconds
        assert event["name"] == name0
        assert event["attributes"].get("string") == "bar"
        assert event["attributes"].get("bool") == "true"
        assert event["attributes"].get("int") == "1"
        assert event["attributes"].get("double") == "2.3"
        assert event["attributes"].get("str_arr") == ["a", "b", "c"]
        assert event["attributes"].get("bool_arr") == ["true", "false"]
        assert event["attributes"].get("int_arr") == ["5", "6"]
        assert event["attributes"].get("double_arr") == ["1.1", "2.2"]

        event = span_events[1]
        assert event["time_unix_nano"] == time1 * 1000  # microseconds to nanoseconds
        assert event["name"] == name1
        assert event["attributes"].get("bool") == "false"
        assert event["attributes"].get("int") == "0"
        assert isinstance(event["attributes"].get("int"), str)
        assert event["attributes"].get("double") == "0.0"
        assert isinstance(event["attributes"].get("double"), str)

    @irrelevant(library="ruby", reason="Does not support v0.7")
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.7", "DD_TRACE_NATIVE_SPAN_EVENTS": "1"}])
    def test_span_with_event_v07(self, library_env, test_agent, test_library):
        """Test adding a span event in the v0.7 format, which support the native attribute representation."""

        self._test_span_with_native_event(library_env, test_agent, test_library)

    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.4", "DD_TRACE_NATIVE_SPAN_EVENTS": "1"}])
    def test_span_with_event_v04(self, library_env, test_agent, test_library):
        """Test adding a span event in the v0.4 format, which support the native attribute representation."""

        self._test_span_with_native_event(library_env, test_agent, test_library)

    @irrelevant(library="ruby", reason="Does not support v0.5")
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.5", "DD_TRACE_NATIVE_SPAN_EVENTS": "1"}])
    def test_span_with_event_v05(self, library_env, test_agent, test_library):
        """Test adding a span event in the v0.5 format, which does not support the native attribute representation.
        Thus span events are serialized as span tags, and attribute values all strings.
        """

        self._test_span_with_meta_event(library_env, test_agent, test_library)

    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.4", "DD_TRACE_NATIVE_SPAN_EVENTS": "1"}])
    def test_span_with_invalid_event_attributes(self, library_env, test_agent, test_library):
        """Test adding a span event, with invalid attributes, to an active span.
        Span events with invalid attributes should be discarded.
        Valid attributes should be kept.
        """

        with test_library, test_library.otel_start_span("test") as s:
            s.add_event(
                "name",
                timestamp=123450,
                attributes={
                    "int": 1,
                    "invalid_arr1": [1, "a"],
                    "invalid_arr2": [[1]],
                    "invalid_int1": 2 << 65,
                    "invalid_int2": -2 << 65,
                    "string": "bar",
                },
            )

        traces = test_agent.wait_for_num_traces(1)

        trace = find_trace(traces, s.trace_id)
        assert len(trace) == 1
        span = find_span(trace, s.span_id)

        span_events = span["span_events"]

        assert len(span_events) == 1

        event = span_events[0]
        assert event["name"] == "name"

        assert len(event["attributes"]) == 2
        assert event["attributes"].get("int").get("int_value") == 1
        assert event["attributes"].get("string").get("string_value") == "bar"

@rfc("https://docs.google.com/document/d/1-7CsG8GZVnNU198FfzavCNMI6IF0cGzFfS8cIz6Pu1g")
@scenarios.parametric
@features.record_exception
class Test_Record_Exception:
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "cpp", reason="Not implemented")
    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.4", "DD_TRACE_NATIVE_SPAN_EVENTS": "1"}])
    def test_span_record_exception(self, test_agent, test_library):
        """Tests the Datadog Span.RecordException API and its serialization
        into the Datadog 'events' tag and 'span' tag
        """
        attributes0 = {
            "string": "bar",
            "bool": True,
            "int": 1,
            "double": 2.3,
            "str_arr": ["a", "b", "c"],
            "bool_arr": [True, False],
            "int_arr": [5, 6],
            "double_arr": [1.1, 2.2],
        }

        attributes1 = {"bool": False, "int": 0, "double": 0.0}

        with test_library, test_library.otel_start_span("test") as s:
            exception_type1 = s.record_exception("TestException1", attributes=attributes0)
            exception_type2 = s.record_exception("TestException2", attributes=attributes1)

        traces = test_agent.wait_for_num_traces(1)

        trace = find_trace(traces, s.trace_id)
        assert len(trace) == 1
        span = find_span(trace, s.span_id)

        span_events = span["span_events"]

        assert len(span_events) == 2

        event = span_events[0]
        assert event["name"] == "exception"
        assert event["exception.type"] == exception_type1
        assert event["exception.message"] == "TestException1"
        assert event["attributes"].get("string") == {"type": 0, "string_value": "bar"}
        assert event["attributes"].get("bool") == {"type": 1, "bool_value": True}
        assert event["attributes"].get("int") == {"type": 2, "int_value": 1}
        assert event["attributes"].get("double") == {"type": 3, "double_value": 2.3}

        assert event["attributes"].get("str_arr") == {
            "type": 4,
            "array_value": {
                "values": [
                    {"type": 0, "string_value": "a"},
                    {"type": 0, "string_value": "b"},
                    {"type": 0, "string_value": "c"},
                ]
            },
        }
        assert event["attributes"].get("bool_arr") == {
            "type": 4,
            "array_value": {"values": [{"type": 1, "bool_value": True}, {"type": 1, "bool_value": False}]},
        }
        assert event["attributes"].get("int_arr") == {
            "type": 4,
            "array_value": {"values": [{"type": 2, "int_value": 5}, {"type": 2, "int_value": 6}]},
        }
        assert event["attributes"].get("double_arr") == {
            "type": 4,
            "array_value": {"values": [{"type": 3, "double_value": 1.1}, {"type": 3, "double_value": 2.2}]},
        }

        event = span_events[1]
        assert event["name"] == "exception"
        assert event["exception.type"] == exception_type2
        assert event["exception.message"] == "TestException2"
        assert event["attributes"].get("bool") == {"type": 1, "bool_value": False}
        assert event["attributes"].get("int") == {"type": 2, "int_value": 0}
        assert isinstance(event["attributes"].get("int").get("int_value"), int)
        assert event["attributes"].get("double") == {"type": 3, "double_value": 0.0}
        assert isinstance(event["attributes"].get("double").get("double_value"), float)

    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "cpp", reason="Not implemented")
    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.4", "DD_TRACE_NATIVE_SPAN_EVENTS": "1"}])
    def test_span_with_invalid_event_attributes(self, test_agent, test_library):
        """Test adding a span event, with invalid attributes, to an active span.
        Span events with invalid attributes should be discarded.
        Valid attributes should be kept.
        """
        with test_library, test_library.otel_start_span("test") as s:
            exception_type = s.record_exception("TestException", attributes={
                    "int": 1,
                    "invalid_arr1": [1, "a"],
                    "invalid_arr2": [[1]],
                    "invalid_int1": 2 << 65,
                    "invalid_int2": -2 << 65,
                    "string": "bar",
                })

        traces = test_agent.wait_for_num_traces(1)

        trace = find_trace(traces, s.trace_id)
        assert len(trace) == 1
        span = find_span(trace, s.span_id)

        span_events = span["span_events"]

        assert len(span_events) == 1

        event = span_events[0]
        assert event["name"] == "exception"

        assert len(event["attributes"]) == 4
        assert event["exception.type"] == exception_type
        assert event["exception.message"] == "TestException"
        assert event["attributes"].get("int").get("int_value") == 1
        assert event["attributes"].get("string").get("string_value") == "bar"


