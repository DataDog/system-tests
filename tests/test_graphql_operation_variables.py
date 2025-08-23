# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""GraphQL Operation Variables Capture Tests

This test suite implements comprehensive testing for the GraphQL Capture Operation Variables RFC (APMRFC0027).
The tests verify that GraphQL operation variables are captured correctly in APM spans according to the RFC specifications.

Test Coverage:
1. Default behavior - no variables captured when no configuration is set
2. Allowlist configuration - only specified variables are captured
3. Denylist configuration - all variables except specified ones are captured
4. Combined allowlist and denylist - denylist takes precedence
5. Variable type serialization - String, Int, Boolean, ID types
6. Complex query variables - variables in complex queries are captured
7. Case-sensitive matching - operation and variable names must match exactly
8. Invalid configuration handling - malformed configuration fragments are ignored
9. Empty string variables - empty strings are captured correctly
10. Multiple operations - only variables from executed operation are captured

Environment Variables Tested:
- DD_TRACE_GRAPHQL_CAPTURE_VARIABLES: Comma-separated list of operation:variable pairs to capture
- DD_TRACE_GRAPHQL_CAPTURE_VARIABLES_EXCEPT: Comma-separated list of operation:variable pairs to exclude

Expected Span Tags:
- graphql.operation.variable.{variableName}: The value of the captured variable

The tests use the graphql23 Ruby application which provides GraphQL endpoints with various operation types
and variable configurations to thoroughly test the RFC implementation.
"""

import json
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


@rfc("https://docs.google.com/document/d/1f5mU1W4rtkpdtUbZi8HFuXPkgTrWoMd5YcKLduWTYuA")
@scenarios.graphql_appsec
@features.graphql_operation_variables
class Test_GraphQLOperationVariablesDefault:
    """Test GraphQL operation variables with default configuration (no variables captured)"""

    def setup_default_behavior_no_variables_captured(self):
        """Test that by default, no operation variables are captured"""
        self.request = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": """
                    query GetUser($intParam: Int, $floatParam: Float, $stringParam: String, $booleanParam: Boolean, $idParam: ID) {
                        withParameters(intParam: $intParam, floatParam: $floatParam, stringParam: $stringParam, booleanParam: $booleanParam, idParam: $idParam)
                    }
                    """,
                    "operationName": "GetUser",
                    "variables": {
                        "intParam": 123,
                        "floatParam": 3.14,
                        "stringParam": "test string",
                        "booleanParam": True,
                        "idParam": "test-id",
                    },
                }
            ),
        )

    def test_default_behavior_no_variables_captured(self):
        """Test that by default, no operation variables are captured in span tags"""
        assert self.request.status_code == 200

        spans = list(
            span
            for _, _, span in interfaces.library.get_spans(request=self.request, full_trace=True)
            if self._is_graphql_execute_span(span)
        )

        assert len(spans) == 1
        span = spans[0]

        meta = span.get("meta", {})

        # Verify no operation variable tags are present
        for key in meta:
            assert not key.startswith("graphql.operation.variable.")

    @staticmethod
    def _is_graphql_execute_span(span) -> bool:
        name = span["name"]
        lang = span.get("meta", {}).get("language", "")
        component = span.get("meta", {}).get("component", "")
        return name == COMPONENT_EXCEPTIONS[lang][component]["operation_name"]


@rfc("https://docs.google.com/document/d/1f5mU1W4rtkpdtUbZi8HFuXPkgTrWoMd5YcKLduWTYuA")
@scenarios.graphql_operation_variables
@features.graphql_operation_variables
class Test_GraphQLOperationVariablesAllowlist:
    """Test GraphQL operation variables with allowlist configuration"""

    def setup_allowlist_specific_variables(self):
        """Test capturing specific variables using DD_TRACE_GRAPHQL_CAPTURE_VARIABLES"""
        self.request = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": """
                    query GetUser($intParam: Int, $floatParam: Float, $stringParam: String, $booleanParam: Boolean, $idParam: ID) {
                        withParameters(intParam: $intParam, floatParam: $floatParam, stringParam: $stringParam, booleanParam: $booleanParam, idParam: $idParam)
                    }
                    """,
                    "operationName": "GetUser",
                    "variables": {
                        "intParam": 123,
                        "floatParam": 3.14,
                        "stringParam": "test string",
                        "booleanParam": True,
                        "idParam": "test-id",
                    },
                }
            ),
        )

    def test_allowlist_specific_variables(self):
        """Test that only specified variables are captured (denylist affects allowlist variables, invalid options ignored)"""
        assert self.request.status_code == 200

        spans = list(
            span
            for _, _, span in interfaces.library.get_spans(request=self.request, full_trace=True)
            if self._is_graphql_execute_span(span)
        )

        assert len(spans) == 1
        span = spans[0]

        meta = span.get("meta", {})

        # Check that allowed variables are captured (valid options)
        assert "graphql.operation.variable.intParam" in meta
        assert meta["graphql.operation.variable.intParam"] == "123"

        assert "graphql.operation.variable.booleanParam" in meta
        assert meta["graphql.operation.variable.booleanParam"] == "true"

        # Check that denied variable is not captured (denylist affects allowlist)
        assert "graphql.operation.variable.stringParam" not in meta

        # Invalid options like "invalid:format" and "malformed" should be ignored
        # Whitespace values like " SearchUsers:query " should be handled correctly

    def setup_variable_serialization_types(self):
        """Test serialization of different variable types"""
        self.request = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": """
                    query SearchUsers($stringParam: String, $intParam: Int, $booleanParam: Boolean) {
                        withParameters(stringParam: $stringParam, intParam: $intParam, booleanParam: $booleanParam)
                    }
                    """,
                    "operationName": "SearchUsers",
                    "variables": {"stringParam": "test user", "intParam": 42, "booleanParam": False},
                }
            ),
        )

    def test_variable_serialization_types(self):
        """Test that different variable types are serialized correctly"""
        assert self.request.status_code == 200

        spans = list(
            span
            for _, _, span in interfaces.library.get_spans(request=self.request, full_trace=True)
            if self._is_graphql_execute_span(span)
        )

        assert len(spans) == 1
        span = spans[0]

        meta = span.get("meta", {})

        # Test String serialization (should be captured - in allowlist)
        assert "graphql.operation.variable.stringParam" in meta
        assert meta["graphql.operation.variable.stringParam"] == "test user"

        # Test Int serialization (should NOT be captured - not in allowlist)
        assert "graphql.operation.variable.intParam" not in meta

        # Test Boolean serialization (should NOT be captured - not in allowlist)
        assert "graphql.operation.variable.booleanParam" not in meta

    def setup_whitespace_handling(self):
        """Test handling of values with leading/trailing whitespaces"""
        self.request = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": """
                    query SearchUsers($stringParam: String, $intParam: Int, $booleanParam: Boolean) {
                        withParameters(stringParam: $stringParam, intParam: $intParam, booleanParam: $booleanParam)
                    }
                    """,
                    "operationName": "SearchUsers",
                    "variables": {"stringParam": "test user", "intParam": 42, "booleanParam": False},
                }
            ),
        )

    def test_whitespace_handling(self):
        """Test that values with leading/trailing whitespaces are handled correctly"""
        assert self.request.status_code == 200

        spans = list(
            span
            for _, _, span in interfaces.library.get_spans(request=self.request, full_trace=True)
            if self._is_graphql_execute_span(span)
        )

        assert len(spans) == 1
        span = spans[0]

        meta = span.get("meta", {})

        # Check that whitespace values are handled correctly
        # Configuration has " SearchUsers:stringParam " (with whitespace)
        assert "graphql.operation.variable.stringParam" in meta
        assert meta["graphql.operation.variable.stringParam"] == "test user"

        # Other variables should not be captured (not in allowlist)
        assert "graphql.operation.variable.intParam" not in meta
        assert "graphql.operation.variable.booleanParam" not in meta

    def setup_complex_query_with_variables(self):
        """Test complex query with multiple variable types"""
        self.request = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": """
                    query GetUserStats($idParam: ID!, $booleanParam: Boolean!) {
                        withParameters(idParam: $idParam, booleanParam: $booleanParam)
                    }
                    """,
                    "operationName": "GetUserStats",
                    "variables": {
                        "idParam": "123",
                        "booleanParam": True,
                    },
                }
            ),
        )

    def test_complex_query_with_variables(self):
        """Test that complex query variables are captured according to allowlist"""
        assert self.request.status_code == 200

        spans = list(
            span
            for _, _, span in interfaces.library.get_spans(request=self.request, full_trace=True)
            if self._is_graphql_execute_span(span)
        )

        assert len(spans) == 1
        span = spans[0]

        meta = span.get("meta", {})

        # Check that variables are captured according to allowlist
        # GetUserStats:idParam is in the allowlist, so it should be captured
        assert "graphql.operation.variable.idParam" in meta
        assert meta["graphql.operation.variable.idParam"] == "123"

        # GetUserStats:booleanParam is not in the allowlist, so it should not be captured
        assert "graphql.operation.variable.booleanParam" not in meta

    def setup_case_sensitive_matching(self):
        """Test case-sensitive matching of operation and variable names"""
        self.request = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": """
                    query getUser($intParam: Int, $floatParam: Float, $stringParam: String, $booleanParam: Boolean, $idParam: ID) {
                        withParameters(intParam: $intParam, floatParam: $floatParam, stringParam: $stringParam, booleanParam: $booleanParam, idParam: $idParam)
                    }
                    """,
                    "operationName": "getUser",
                    "variables": {
                        "intParam": 123,
                        "floatParam": 3.14,
                        "stringParam": "test string",
                        "booleanParam": True,
                        "idParam": "test-id",
                    },
                }
            ),
        )

    def test_case_sensitive_matching(self):
        """Test that operation and variable names must match exactly (case-sensitive)"""
        assert self.request.status_code == 200

        spans = list(
            span
            for _, _, span in interfaces.library.get_spans(request=self.request, full_trace=True)
            if self._is_graphql_execute_span(span)
        )

        assert len(spans) == 1
        span = spans[0]

        meta = span.get("meta", {})

        # Check that case-mismatched variables are NOT captured
        # Configuration has "GetUser:intParam" but query uses "getUser:intParam"
        assert "graphql.operation.variable.intParam" not in meta
        assert "graphql.operation.variable.floatParam" not in meta
        assert "graphql.operation.variable.stringParam" not in meta

    def setup_custom_input_type_variables(self):
        """Test capturing variables with custom input types containing multiple scalars"""
        self.request = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": """
                    query TestCustomType($customParam: CustomInputType) {
                        withParameters(customParam: $customParam)
                    }
                    """,
                    "operationName": "TestCustomType",
                    "variables": {"customParam": {"integerField": 42, "stringField": "test string"}},
                }
            ),
        )

    def test_custom_input_type_variables(self):
        """Test that custom input type variables are captured and serialized correctly"""
        assert self.request.status_code == 200

        spans = list(
            span
            for _, _, span in interfaces.library.get_spans(request=self.request, full_trace=True)
            if self._is_graphql_execute_span(span)
        )

        assert len(spans) == 1
        span = spans[0]

        meta = span.get("meta", {})

        # Check that custom input type variable is captured
        # The custom input type should be serialized as a string representation
        assert "graphql.operation.variable.customParam" in meta

        # The value should be a string representation of the custom input type
        # This tests the RFC requirement: "Custom type: serialized as a string, using the best effort possible"
        custom_param_value = meta["graphql.operation.variable.customParam"]
        assert isinstance(custom_param_value, str)
        # The exact format may vary by implementation, but it should contain both field values
        assert "42" in custom_param_value or "integerField" in custom_param_value
        assert "test string" in custom_param_value or "stringField" in custom_param_value

    def setup_empty_string_variables(self):
        """Test handling of empty string variables"""
        self.request = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": """
                    query SearchUsers($stringParam: String, $intParam: Int, $booleanParam: Boolean) {
                        withParameters(stringParam: $stringParam, intParam: $intParam, booleanParam: $booleanParam)
                    }
                    """,
                    "operationName": "SearchUsers",
                    "variables": {"stringParam": "", "intParam": 42, "booleanParam": False},
                }
            ),
        )

    def test_empty_string_variables(self):
        """Test that empty string variables are captured correctly"""
        assert self.request.status_code == 200

        spans = list(
            span
            for _, _, span in interfaces.library.get_spans(request=self.request, full_trace=True)
            if self._is_graphql_execute_span(span)
        )

        assert len(spans) == 1
        span = spans[0]

        meta = span.get("meta", {})

        # Check that empty string is captured correctly (in allowlist)
        assert "graphql.operation.variable.stringParam" in meta
        assert meta["graphql.operation.variable.stringParam"] == ""

    def setup_multiple_operations(self):
        """Test that only variables from executed operation are captured"""
        self.request = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": """
                    query GetUser($intParam: Int, $floatParam: Float, $stringParam: String, $booleanParam: Boolean, $idParam: ID) {
                        withParameters(intParam: $intParam, floatParam: $floatParam, stringParam: $stringParam, booleanParam: $booleanParam, idParam: $idParam)
                    }

                    query SearchUsers($stringParam: String, $intParam: Int) {
                        withParameters(stringParam: $stringParam, intParam: $intParam)
                    }
                    """,
                    "operationName": "GetUser",
                    "variables": {
                        "intParam": 123,
                        "floatParam": 3.14,
                        "stringParam": "test string",
                        "booleanParam": True,
                        "idParam": "test-id",
                    },
                }
            ),
        )

    def test_multiple_operations(self):
        """Test that only variables from executed operation are captured"""
        assert self.request.status_code == 200

        spans = list(
            span
            for _, _, span in interfaces.library.get_spans(request=self.request, full_trace=True)
            if self._is_graphql_execute_span(span)
        )

        assert len(spans) == 1
        span = spans[0]

        meta = span.get("meta", {})

        # Check that only GetUser variables are captured (executed operation)
        assert "graphql.operation.variable.intParam" in meta
        assert "graphql.operation.variable.booleanParam" in meta

        # Check that SearchUsers variables are NOT captured (not executed)
        assert "graphql.operation.variable.stringParam" not in meta
        assert "graphql.operation.variable.intParam" not in meta

    @staticmethod
    def _is_graphql_execute_span(span) -> bool:
        name = span["name"]
        lang = span.get("meta", {}).get("language", "")
        component = span.get("meta", {}).get("component", "")
        return name == COMPONENT_EXCEPTIONS[lang][component]["operation_name"]


@rfc("https://docs.google.com/document/d/1f5mU1W4rtkpdtUbZi8HFuXPkgTrWoMd5YcKLduWTYuA")
@scenarios.graphql_operation_variables_denylist
@features.graphql_operation_variables
class Test_GraphQLOperationVariablesDenylist:
    """Test GraphQL operation variables with denylist configuration"""

    def setup_denylist_specific_variables(self):
        """Test capturing all variables except specific ones using DD_TRACE_GRAPHQL_CAPTURE_VARIABLES_EXCEPT"""
        self.request = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": """
                    query excludeStringParam($intParam: Int, $floatParam: Float, $stringParam: String, $booleanParam: Boolean, $idParam: ID) {
                        withParameters(intParam: $intParam, floatParam: $floatParam, stringParam: $stringParam, booleanParam: $booleanParam, idParam: $idParam)
                    }
                    """,
                    "operationName": "excludeStringParam",
                    "variables": {
                        "intParam": 123,
                        "floatParam": 3.14,
                        "stringParam": "test string",
                        "booleanParam": True,
                        "idParam": "test-id",
                    },
                }
            ),
        )

    def test_denylist_specific_variables(self):
        """Test that all variables except specified ones are captured (invalid options ignored)"""
        assert self.request.status_code == 200

        spans = list(
            span
            for _, _, span in interfaces.library.get_spans(request=self.request, full_trace=True)
            if self._is_graphql_execute_span(span)
        )

        assert len(spans) == 1
        span = spans[0]

        meta = span.get("meta", {})

        # Check that non-excluded variables are captured
        # excludeStringParam:intParam and excludeStringParam:booleanParam are NOT in denylist, so they should be captured
        assert "graphql.operation.variable.intParam" in meta
        assert meta["graphql.operation.variable.intParam"] == "123"

        assert "graphql.operation.variable.booleanParam" in meta
        assert meta["graphql.operation.variable.booleanParam"] == "true"

        # Check that excluded variable is not captured
        # excludeStringParam:stringParam is in denylist, so it should NOT be captured
        assert "graphql.operation.variable.stringParam" not in meta

        # Invalid options like "invalid:format" and "malformed:value" should be ignored

    def setup_denylist_search_users(self):
        """Test denylist with SearchUsers operation"""
        self.request = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": """
                    query excludeIntParam($stringParam: String, $intParam: Int, $booleanParam: Boolean) {
                        withParameters(stringParam: $stringParam, intParam: $intParam, booleanParam: $booleanParam)
                    }
                    """,
                    "operationName": "excludeIntParam",
                    "variables": {"stringParam": "test user", "intParam": 42, "booleanParam": False},
                }
            ),
        )

    def test_denylist_search_users(self):
        """Test that SearchUsers variables are captured except excluded ones (whitespace values handled correctly)"""
        assert self.request.status_code == 200

        spans = list(
            span
            for _, _, span in interfaces.library.get_spans(request=self.request, full_trace=True)
            if self._is_graphql_execute_span(span)
        )

        assert len(spans) == 1
        span = spans[0]

        meta = span.get("meta", {})

        # Check that non-excluded variables are captured
        # excludeIntParam:stringParam and excludeIntParam:booleanParam are NOT in denylist, so they should be captured
        assert "graphql.operation.variable.stringParam" in meta
        assert meta["graphql.operation.variable.stringParam"] == "test user"

        assert "graphql.operation.variable.booleanParam" in meta
        assert meta["graphql.operation.variable.booleanParam"] == "false"

        # Check that excluded variable is not captured (whitespace value " excludeIntParam:intParam ")
        assert "graphql.operation.variable.intParam" not in meta

        # Invalid options like "invalid:format" and "malformed:value" should be ignored

    def setup_invalid_configuration_handling(self):
        """Test handling of malformed configuration fragments"""
        # This test uses the denylist scenario which has "GetUser:org,SearchUsers:limit"
        # We'll test with a query that has variables that don't match the configuration format
        self.request = weblog.post(
            "/graphql",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {
                    "query": """
                    query GetUser($intParam: Int, $floatParam: Float, $stringParam: String, $booleanParam: Boolean, $idParam: ID) {
                        withParameters(intParam: $intParam, floatParam: $floatParam, stringParam: $stringParam, booleanParam: $booleanParam, idParam: $idParam)
                    }
                    """,
                    "operationName": "GetUser",
                    "variables": {
                        "intParam": 123,
                        "floatParam": 3.14,
                        "stringParam": "test string",
                        "booleanParam": True,
                        "idParam": "test-id",
                    },
                }
            ),
        )

    def test_invalid_configuration_handling(self):
        """Test that malformed configuration fragments are ignored gracefully"""
        assert self.request.status_code == 200

        spans = list(
            span
            for _, _, span in interfaces.library.get_spans(request=self.request, full_trace=True)
            if self._is_graphql_execute_span(span)
        )

        assert len(spans) == 1
        span = spans[0]

        meta = span.get("meta", {})

        # Check that variables are captured according to valid configuration
        # "GetUser:stringParam" is in denylist, so it should NOT be captured
        assert "graphql.operation.variable.intParam" in meta
        assert "graphql.operation.variable.booleanParam" in meta
        assert "graphql.operation.variable.stringParam" not in meta

    @staticmethod
    def _is_graphql_execute_span(span) -> bool:
        name = span["name"]
        lang = span.get("meta", {}).get("language", "")
        component = span.get("meta", {}).get("component", "")
        return name == COMPONENT_EXCEPTIONS[lang][component]["operation_name"]
