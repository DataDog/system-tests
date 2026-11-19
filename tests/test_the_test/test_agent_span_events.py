"""Unit tests for DataDogAgentSpan.get_span_events(), which normalizes the different ways the agent
can carry span events to the backend.
"""

import base64
import json

from utils import pytest
from utils.proxy.traces.trace_v1 import _uncompress_agent_v1_trace
from utils.dd_types import DataDogAgentSpan, DataDogAgentTrace


pytestmark = pytest.mark.scenario("TEST_THE_TEST")

EXPECTED_EVENTS = [
    {
        "name": "exception",
        "time_unix_nano": 1794607861156080339,
        "attributes": {
            "exception.type": "ValueError",
            "exception.message": "boom",
            "exception.escaped": False,
            "attempt": 2,
            "ratio": 0.5,
            "tags": ["a", "b"],
        },
    }
]


def _legacy_span(span: dict) -> DataDogAgentSpan:
    return DataDogAgentTrace.from_agent_legacy({}, {"spans": [span]}).spans[0]


def _v1_span(span: dict) -> DataDogAgentSpan:
    return DataDogAgentTrace.from_agent_v1({}, {"spans": [span]}).spans[0]


def test_legacy_meta_events():
    """Agents before DataDog/datadog-agent#59621 send OTLP span events as a JSON string in the events tag"""
    span = _legacy_span({"meta": {"events": json.dumps(EXPECTED_EVENTS)}})
    assert span.get_span_events() == EXPECTED_EVENTS


def test_legacy_native_span_events():
    """datadog.trace.SpanEvent as deserialized by MessageToDict: default values (STRING_VALUE type,
    false bool...) are omitted, and int64 are strings
    """
    span = _legacy_span(
        {
            "meta": {"_dd.span_events.has_exception": "true"},
            "spanEvents": [
                {
                    "timeUnixNano": "1794607861156080339",
                    "name": "exception",
                    "attributes": {
                        "exception.type": {"stringValue": "ValueError"},
                        "exception.message": {"stringValue": "boom"},
                        "exception.escaped": {"type": "BOOL_VALUE"},
                        "attempt": {"type": "INT_VALUE", "intValue": "2"},
                        "ratio": {"type": "DOUBLE_VALUE", "doubleValue": 0.5},
                        "tags": {
                            "type": "ARRAY_VALUE",
                            "arrayValue": {"values": [{"stringValue": "a"}, {"stringValue": "b"}]},
                        },
                    },
                }
            ],
        }
    )
    assert span.get_span_events() == EXPECTED_EVENTS


def test_legacy_native_span_events_take_precedence():
    span = _legacy_span({"meta": {"events": "[]"}, "spanEvents": [{"name": "exception"}]})
    assert span.get_span_events() == [{"name": "exception", "time_unix_nano": 0, "attributes": {}}]


def test_legacy_unknown_attribute_type():
    span = _legacy_span({"meta": {}, "spanEvents": [{"name": "e", "attributes": {"k": {"type": "NOPE"}}}]})
    with pytest.raises(ValueError, match="Unsupported span event attribute type"):
        span.get_span_events()


def test_v1_native_span_events():
    """idx.SpanEvent as deserialized by MessageToDict, then post-processed by the proxy"""
    strings = ["", "exception", "exception.type", "ValueError", "exception.message", "boom", "exception.escaped"]
    strings += ["attempt", "ratio", "tags", "a", "b"]
    data = {
        "idxTracerPayloads": [
            {
                "strings": strings,
                "chunks": [
                    {
                        "traceID": base64.b64encode(bytes(16)).decode("utf-8"),
                        "spans": [
                            {
                                "events": [
                                    {
                                        "time": "1794607861156080339",
                                        "nameRef": 1,
                                        "attributes": {
                                            "2": {"stringValueRef": 3},
                                            "4": {"stringValueRef": 5},
                                            "6": {"boolValue": False},
                                            "7": {"intValue": "2"},
                                            "8": {"doubleValue": 0.5},
                                            "9": {
                                                "arrayValue": {
                                                    "values": [{"stringValueRef": 10}, {"stringValueRef": 11}]
                                                }
                                            },
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }

    chunk = _uncompress_agent_v1_trace(data, "agent")["idxTracerPayloads"][0]["chunks"][0]
    span = DataDogAgentTrace.from_agent_v1({}, chunk).spans[0]
    assert span.get_span_events() == EXPECTED_EVENTS


def test_v1_meta_events():
    span = _v1_span({"attributes": {"events": json.dumps(EXPECTED_EVENTS)}})
    assert span.get_span_events() == EXPECTED_EVENTS


def test_no_events():
    assert _legacy_span({"meta": {}}).get_span_events() == []
    assert _v1_span({"attributes": {}}).get_span_events() == []
