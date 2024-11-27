import json
import pytest

from utils import scenarios, missing_feature, features, rfc
from utils.parametric._library_client import Event
from utils.parametric.spec.trace import find_span, find_trace


@rfc("https://docs.google.com/document/d/1cVod_VI7Yruq8U9dfMRFJd7npDu-uBpste2IB04GyaQ")
@scenarios.parametric
@features.span_events
@missing_feature(reason="Agent does not advertise native span events serialization support yet")
class Test_Span_Events:
    def _test_span_with_event(self, _library_env, test_agent, test_library, retrieve_events):
        """Test adding a span event, with attributes, to an active span.
        """
        time0 = 123450
        name0 = "event_name"
        attributes0 = {
            "string": "bar",
            "bool": True,
            "int": 1,
            "double": 2.3,
            "array": ["a", "b", "c"],
        }

        time1 = 123451
        name1 = "other_event"
        attributes1 = {
            "bool": False,
            "int": 0,
            "double": 0.0,
            "array": [5, 6],
        }

        with test_library:
            with test_library.otel_start_span("test") as s:
                s.add_event(name0, timestamp=time0, attributes=attributes0)
                s.add_event(name1, timestamp=time1, attributes=attributes1)

        traces = test_agent.wait_for_num_traces(1)

        trace = find_trace(traces, s.trace_id)
        assert len(trace) == 1
        span = find_span(trace, s.span_id)

        span_events = retrieve_events(span)

        assert len(span_events) == 2

        event = span_events[0]
        assert event["time_unix_nano"] == time0 * 1000
        assert event["name"] == name0
        assert event["attributes"].get("string") == {"type": 0, "string_value": "bar"}
        assert event["attributes"].get("bool") == {"type": 1, "bool_value": True}
        assert event["attributes"].get("int") == {"type": 2, "int_value": 1}
        assert event["attributes"].get("double") == {"type": 3, "double_value": 2.3}
        assert event["attributes"].get("array") == {
            "type": 4,
            "array_value": {"type": 0, "string_value": ["a", "b", "c"]},
        }

        event = span_events[1]
        assert event["time_unix_nano"] == time1 * 1000
        assert event["name"] == name1
        assert event["attributes"].get("bool") == {"type": 1, "bool_value": False}
        assert event["attributes"].get("int") == {"type": 2, "int_value": 0}
        assert isinstance(event["attributes"].get("int").get("int"), int)
        assert event["attributes"].get("double") == {"type": 3, "double_value": 0.0}
        assert isinstance(event["attributes"].get("double").get("double"), float)
        assert event["attributes"].get("array") == {"type": 4, "array_value": {"type": 2, "int_value": [5, 6]}}

    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_API_VERSION": "v0.7"}],
    )
    def test_span_with_event_v07(self, library_env, test_agent, test_library):
        """Test adding a span event in the v0.4 and v0.5, which support the native attribute representation.
        """

        self._test_span_with_event(library_env, test_agent, test_library, lambda span: span["span_events"])

    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_API_VERSION": "v0.4"}],
    )
    def test_span_with_event_v04(self, library_env, test_agent, test_library):
        """Test adding a span event in the v0.4 and v0.5, which support the native attribute representation.
        """

        self._test_span_with_event(library_env, test_agent, test_library, lambda span: span["span_events"])

    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.5"}])
    def test_span_with_event_v05(self, library_env, test_agent, test_library):
        """Test adding a span event in the v0.5 format, which does not support the native attribute representation.
        Thus span events are serialized as span tags.
        """

        self._test_span_with_event(
            library_env, test_agent, test_library, lambda span: json.loads(span.get("meta", {}).get("events"))
        )

    def test_span_with_invalid_event_attributes(self, library_env, test_agent, test_library):
        """Test adding a span event, with invalid attributes, to an active span.
        Span events with invalid attributes should be discarded.
        """

        with test_library:
            with test_library.dd_start_span("test") as s:
                s.add_event(
                    "name",
                    timestamp=123,
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
