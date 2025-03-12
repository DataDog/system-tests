# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
from typing import Any
from utils import (
    interfaces,
    rfc,
    weblog,
    features,
    scenarios,
)
from collections import defaultdict

COMPONENT_EXCEPTIONS: defaultdict[str, defaultdict[str, dict]] = defaultdict(
    lambda: defaultdict(lambda: {"operation_name": "graphql.execute", "has_location": True})
)

COMPONENT_EXCEPTIONS["go"]["99designs/gqlgen"] = {
    "operation_name": "graphql.query",
    "has_location": False,
}

COMPONENT_EXCEPTIONS["go"]["graph-gophers/graphql-go"] = {
    "operation_name": "graphql.request",
    "has_location": False,
}


@rfc("https://docs.google.com/document/d/1JjctLYE4a4EbtmnFixQt-TilltcSV69IAeiSGjcUL34")
@scenarios.graphql_appsec
@features.graphql_query_error_reporting
class Test_GraphQLQueryErrorReporting:
    """Test if GraphQL query errors create span events"""

    def setup_execute_error_span_event(self):
        self.request = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": "query myQuery { withError }",
                    "operationName": "myQuery",
                }
            ),
        )

    def test_execute_error_span_event(self):
        """Test if the main GraphQL span contains a span event with the appropriate error information.
        The /graphql endpoint must support the query `query myQuery { withError }` which will return an
        error response with the following structure:
        {
            "errors": [
                {
                    "message": <the application error message (string)>,
                    "locations": [
                        {
                            "line": <line number (int)>,
                            "column": <column number (int)>
                        }
                    ],
                    "path": <path to the field in the query (array of strings)>,
                    "extensions": {
                        "int": 1,
                        "float": 1.1,
                        "str": "1",
                        "bool": true,
                        "other": [1, "foo"],
                        "not_captured": <any value>
                    }
                }
            ],
            "data": <may or may not be present, GraphQL-library dependent>
        }
        The error extensions allowed in this test are DD_TRACE_GRAPHQL_ERROR_EXTENSIONS=int,float,str,bool,other.
        """

        assert self.request.status_code == 200

        spans = list(
            span
            for _, _, span in interfaces.library.get_spans(request=self.request, full_trace=True)
            if self._is_graphql_execute_span(span)
        )

        assert len(spans) == 1
        span = spans[0]

        events = self._get_events(span)
        graphql_events = [event for event in events if event["name"] == "dd.graphql.query.error"]

        assert len(graphql_events) == 1
        event = graphql_events[0]

        assert event["name"] == "dd.graphql.query.error"

        attributes = event["attributes"]

        assert attributes["message"]["type"] == 0
        assert attributes["message"]["string_value"] == "test error"

        assert attributes["type"]["type"] == 0
        assert attributes["type"].get("string_value", "") != ""

        assert attributes["stacktrace"]["type"] == 0
        assert attributes["stacktrace"].get("string_value", "") != ""

        self._assert_path(attributes)

        if self._has_location(span):
            self._assert_location(attributes)
        else:
            assert "location" not in attributes

        assert attributes["extensions.int"]["type"] == 2
        assert attributes["extensions.int"]["int_value"] == 1

        assert attributes["extensions.float"]["type"] == 3
        assert attributes["extensions.float"]["double_value"] == 1.1

        assert attributes["extensions.str"]["type"] == 0
        assert attributes["extensions.str"]["string_value"] == "1"

        assert attributes["extensions.bool"]["type"] == 1
        assert attributes["extensions.bool"]["bool_value"] == True  # noqa: E712

        # A list with two heterogeneous elements: [1, "foo"].
        # This test simulates an object that is not a supported scalar above (int,float,string,boolean).
        # This object should be serialized as a string, either using the language's default serialization or
        # JSON serialization of the object.
        # The goal here is to display the original data with as much fidelity as possible, without allowing
        # for arbitrary nested levels inside `span_event.attributes`.
        assert attributes["extensions.other"]["type"] == 0
        assert "1" in attributes["extensions.other"]["string_value"]
        assert "foo" in attributes["extensions.other"]["string_value"]

        assert "extensions.not_captured" not in attributes

    @staticmethod
    def _is_graphql_execute_span(span) -> bool:
        name = span["name"]
        lang = span["meta"]["language"]
        component = span["meta"]["component"]
        return name == COMPONENT_EXCEPTIONS[lang][component]["operation_name"]

    @staticmethod
    def _has_location(span) -> bool:
        lang = span["meta"]["language"]
        component = span["meta"]["component"]
        return COMPONENT_EXCEPTIONS[lang][component]["has_location"]

    @staticmethod
    def _assert_path(attributes) -> None:
        assert attributes["path"]["type"] == 4
        path = attributes["path"]["array_value"]["values"]
        assert path is not None
        assert len(path) == 1
        assert path[0]["type"] == 0
        assert path[0]["string_value"] == "withError"

    @staticmethod
    def _assert_location(attributes) -> None:
        assert attributes["location"]["type"] == 4
        location = attributes["location"]["array_value"]["values"]
        assert location is not None
        assert len(location) == 1

        for loc in location:
            assert loc["type"] == 0
            loc_value = loc["string_value"]
            assert len(loc_value.split(":")) == 2
            assert loc_value.split(":")[0].isdigit()
            assert loc_value.split(":")[1].isdigit()

    @staticmethod
    def _get_events(span) -> dict:
        if "events" in span["meta"]:
            return json.loads(span["meta"]["events"])
        else:
            events = span["span_events"]
            for event in events:
                attributes = event["attributes"]

                for key, value in attributes.items():
                    attributes[key] = Test_GraphQLQueryErrorReporting._parse_event_value(value)

            return events

    @staticmethod
    def _parse_event_value(value) -> int | str | bool | float | list[Any]:
        type_ = value["type"]
        if type_ == 0:
            return value["string_value"]
        elif type_ == 1:
            return value["bool_value"]
        elif type_ == 2:
            return value["int_value"]
        elif type_ == 3:
            return value["double_value"]
        elif type_ == 4:
            return [Test_GraphQLQueryErrorReporting._parse_event_value(v) for v in value["array_value"]]
        else:
            raise ValueError(f"Unsupported span event attribute type {type_} for: {value}")
