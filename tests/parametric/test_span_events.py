import json
import pytest

from utils.parametric.spec.trace import ORIGIN
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY
from utils.parametric.spec.trace import AUTO_DROP_KEY
from utils.parametric.spec.trace import span_has_no_parent
from utils.parametric.spec.tracecontext import TRACECONTEXT_FLAGS_SET
from utils import scenarios, missing_feature
from utils.parametric._library_client import Event
from utils.parametric.spec.trace import retrieve_span_events, find_span, find_trace


@scenarios.parametric
class Test_Span_Events:
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.4"}, {"DD_TRACE_API_VERSION": "v0.7"}])
    @missing_feature(library="python", reason="native serialization not implemented")
    def test_span_with_event(self, test_agent, test_library):
        """Test adding a span event in the v0.4 or v0.7 format.
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
            with test_library.start_span("test", events=[
              Event(time_unix_nano=time0, name=name0, attributes=attributes0),
              Event(time_unix_nano=time1, name=name1, attributes=attributes1),
            ]) as s:
                pass

        traces = test_agent.wait_for_num_traces(1)

        trace = find_trace(traces, s.trace_id)
        assert len(trace) == 1
        span = find_span(trace, s.span_id)

        span_events = span["span_events"]

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

    @pytest.mark.parametrize("library_env", [{"DD_TRACE_API_VERSION": "v0.5"}])
    def test_span_with_event_v05(self, test_agent, test_library):
        """Test adding a span event in the v0.5 format.
        This format is not flexible enough to support the native attribute representation,
        thus attributes serialized as span tags.
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
            with test_library.start_span("test", events=[
              Event(time_unix_nano=time0, name=name0, attributes=attributes0),
              Event(time_unix_nano=time1, name=name1, attributes=attributes1),
            ]) as s:
                pass

        traces = test_agent.wait_for_num_traces(1)

        trace = find_trace(traces, s.trace_id)
        assert len(trace) == 1
        span = find_span(trace, s.span_id)

        span_events = json.loads(span.get("meta", {}).get("events"))

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
