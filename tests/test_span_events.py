# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, weblog, interfaces, features


@scenarios.agent_not_supporting_span_events
class Test_SpanEvents:
    """TODO"""

    def test_span_events_v04(self):
        """TODO"""
        interfaces.agent.assert_use_domain(context.dd_site)

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
