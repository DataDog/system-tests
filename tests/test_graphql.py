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


class BaseGraphQLOperationError:
    """Base class for GraphQL query error reporting tests"""

    event_name: str
    message_key: str
    type_key: str
    stacktrace_key: str
    path_key: str
    locations_key: str
    extensions_prefix: str

    @classmethod
    def setup_class(cls) -> None:
        cls._setup_configuration()

    @classmethod
    def _setup_configuration(cls) -> None:
        raise NotImplementedError("Derived classes must implement _setup_configuration")

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
        """Test if the main GraphQL span contains a span event with the appropriate error information."""

        assert self.request.status_code == 200

        spans = list(
            span
            for _, _, span in interfaces.library.get_spans(request=self.request, full_trace=True)
            if self._is_graphql_execute_span(span)
        )

        assert len(spans) == 1
        span = spans[0]

        events = self._get_events(span)
        target_events = [event for event in events if event["name"] == self.event_name]

        assert len(target_events) == 1
        event = target_events[0]

        assert event["name"] == self.event_name

        attributes = event["attributes"]

        self._validate_exception_attributes(attributes)
        self._validate_graphql_attributes(attributes, span)
        self._validate_extensions(attributes)

    def _validate_exception_attributes(self, attributes: dict) -> None:
        """Validate the exception attributes (message, type, stacktrace)"""
        assert isinstance(attributes[self.message_key], str)
        assert isinstance(attributes[self.type_key], str)
        assert isinstance(attributes[self.stacktrace_key], str)

    def _validate_graphql_attributes(self, attributes: dict, span: dict) -> None:
        """Validate GraphQL-specific attributes (path, locations)"""
        for path in attributes[self.path_key]:
            assert isinstance(path, str)

        if self._has_location(span):
            location = attributes[self.locations_key]
            assert len(location) == 1

            for loc in location:
                assert len(loc.split(":")) == 2
                assert loc.split(":")[0].isdigit()
                assert loc.split(":")[1].isdigit()

    def _validate_extensions(self, attributes: dict) -> None:
        """Validate extension attributes"""
        assert attributes[f"{self.extensions_prefix}.int"] == 1
        assert attributes[f"{self.extensions_prefix}.float"] == 1.1
        assert attributes[f"{self.extensions_prefix}.str"] == "1"
        assert attributes[f"{self.extensions_prefix}.bool"] is True

        # A list with two heterogeneous elements: [1, "foo"].
        # This test simulates an object that is not a supported scalar above (int,float,string,boolean).
        # This object should be serialized as a string, either using the language's default serialization or
        # JSON serialization of the object.
        # The goal here is to display the original data with as much fidelity as possible, without allowing
        # for arbitrary nested levels inside `span_event.attributes`.
        assert "1" in attributes[f"{self.extensions_prefix}.other"]
        assert "foo" in attributes[f"{self.extensions_prefix}.other"]

        assert f"{self.extensions_prefix}.not_captured" not in attributes

    @staticmethod
    def _is_graphql_execute_span(span) -> bool:
        name = span["name"]
        lang = span.get("meta", {}).get("language", "")
        component = span.get("meta", {}).get("component", "")
        return name == COMPONENT_EXCEPTIONS[lang][component]["operation_name"]

    @staticmethod
    def _has_location(span) -> bool:
        lang = span.get("meta", {}).get("language", "")
        component = span.get("meta", {}).get("component", "")
        return COMPONENT_EXCEPTIONS[lang][component]["has_location"]

    @staticmethod
    def _get_events(span) -> dict:
        if "events" in span["meta"]:
            return json.loads(span["meta"]["events"])
        else:
            events = span["span_events"]
            for event in events:
                attributes = event["attributes"]

                for key, value in attributes.items():
                    attributes[key] = BaseGraphQLOperationError._parse_event_value(value)

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
            return [BaseGraphQLOperationError._parse_event_value(v) for v in value["array_value"]["values"]]
        else:
            raise ValueError(f"Unsupported span event attribute type {type_} for: {value}")


@rfc("https://docs.google.com/document/d/1JjctLYE4a4EbtmnFixQt-TilltcSV69IAeiSGjcUL34")
@scenarios.graphql_appsec
@features.graphql_operation_error_reporting
class Test_GraphQLOperationErrorReporting(BaseGraphQLOperationError):
    """Test that GraphQL operation errors create span events with the Datadog-specific semantics"""

    @classmethod
    def _setup_configuration(cls) -> None:
        cls.event_name = "dd.graphql.query.error"
        cls.message_key = "message"
        cls.type_key = "type"
        cls.stacktrace_key = "stacktrace"
        cls.path_key = "path"
        cls.locations_key = "locations"
        cls.extensions_prefix = "extensions"


@rfc("https://docs.google.com/document/d/1v_GMkCLltrUuQNex3DRJ2G8UVrR03HvG8WBRnNOC4po")
@scenarios.graphql_error_tracking
@features.graphql_operation_error_tracking
class Test_GraphQLOperationErrorTracking(BaseGraphQLOperationError):
    """Test that GraphQL operation errors create span events with the OpenTelemetry semantics"""

    @classmethod
    def _setup_configuration(cls) -> None:
        cls.event_name = "exception"
        cls.message_key = "exception.message"
        cls.type_key = "exception.type"
        cls.stacktrace_key = "exception.stacktrace"
        cls.path_key = "graphql.error.path"
        cls.locations_key = "graphql.error.locations"
        cls.extensions_prefix = "graphql.error.extensions"
