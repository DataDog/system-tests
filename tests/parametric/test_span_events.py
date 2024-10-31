import json
import pytest

from utils import scenarios, missing_feature, features, rfc
from utils.parametric._library_client import Event
from utils.parametric.spec.trace import find_span, find_trace


@rfc("https://docs.google.com/document/d/1cVod_VI7Yruq8U9dfMRFJd7npDu-uBpste2IB04GyaQ")
@scenarios.parametric
@features.span_events
class Test_Span_Events:
    def _test_span_with_event(self, library_env, test_agent, test_library, retrieve_events):
        """Test adding a span event, with attributes, to an active span.
        """
        time0 = 1234567890
        name0 = "event_name"
        attributes0 = {
            "string": "bar",
            "bool": True,
            "int": 1,
            "double": 2.3,
            "array": ["a", "b", "c"],
        }

        time1 = 1234567891
        name1 = "other_event"
        attributes1 = {
            "bool": False,
            "int": 0,
            "double": 0.0,
            "array": [5, 6],
        }

        with test_library:
            with test_library.start_span(
                "test",
                events=[
                    Event(time_unix_nano=time0, name=name0, attributes=attributes0),
                    Event(time_unix_nano=time1, name=name1, attributes=attributes1),
                ],
            ) as s:
                pass

        traces = test_agent.wait_for_num_traces(1)

        trace = find_trace(traces, s.trace_id)
        assert len(trace) == 1
        span = find_span(trace, s.span_id)

        span_events = retrieve_events(span)

        assert len(span_events) == 2

        event = span_events[0]
        assert event["time_unix_nano"] == time0
        assert event["name"] == name0
        assert event["attributes"].get("string") == "bar"
        assert event["attributes"].get("bool") == True
        assert event["attributes"].get("int") == 1
        assert event["attributes"].get("double") == 2.3
        assert event["attributes"].get("array") == ["a", "b", "c"]

        event = span_events[1]
        assert event["time_unix_nano"] == time1
        assert event["name"] == name1
        assert event["attributes"].get("bool") == False
        assert event["attributes"].get("int") == 0
        assert isinstance(event["attributes"].get("int"), int)
        assert event["attributes"].get("double") == 0.0
        assert isinstance(event["attributes"].get("double"), float)
        assert event["attributes"].get("array") == [5, 6]

    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_API_VERSION": "v0.4"}, {"DD_TRACE_API_VERSION": "v0.7"}],
    )
    def test_span_with_event(self, library_env, test_agent, test_library):
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

    #     @pytest.mark.parametrize("agent_config", [{"SPAN_EVENTS_FLAG": "False"}]) # TODO: How to change the agent config?
    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_API_VERSION": "v0.4"}, {"DD_TRACE_API_VERSION": "v0.7"}],
    )
    def test_span_with_event_old_agent(self, library_env, test_agent, test_library):
        """Test adding a span event when the agent does not support
        the native attribute representation, but the tracer does.
        """

        self._test_span_with_event(
            library_env, test_agent, test_library, lambda span: json.loads(span.get("meta", {}).get("events"))
        )

    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_API_VERSION": "v0.4"}],
    )
    def test_span_with_invalid_event_attributes(self, library_env, test_agent, test_library, retrieve_events):
        """Test adding a span event, with invalid attributes, to an active span.
        Span events with invalid attributes should be discarded.
        """

        with test_library:
            with test_library.start_span(
                "test",
                events=[
                    Event(time_unix_nano=123, name="name", attributes={
            "int": 1,
            "invalid_arr1": [1, "a"], # Heterogeneous arrays are invalid
            "invalid_arr2": [[1]], # Nested arrays are invalid
            "invalid_int1": 2<<65, # Integers outside of a 64-bit (signed) are invalid
            "invalid_int2": -2<<65, # Integers outside of a 64-bit (signed) are invalid
            "string": "bar",
        })
                ],
            ) as s:
                pass

        traces = test_agent.wait_for_num_traces(1)

        trace = find_trace(traces, s.trace_id)
        assert len(trace) == 1
        span = find_span(trace, s.span_id)

        span_events = span["span_events"]

        assert len(span_events) == 1

        event = span_events[0]
        assert event["name"] == "name"

        assert len(event["attributes"]) == 2
        assert event["attributes"].get("string") == "bar"
        assert event["attributes"].get("int") == 1
