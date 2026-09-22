# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import re

import tests.debugger.utils as debugger
from tests.debugger.utils import Dsl, Segment, create_expression_probes, get_type
from utils import scenarios, features, slow


@features.debugger_expression_language
@scenarios.debugger_expression_language
@slow
class Test_Debugger_Expression_Language(debugger.BaseDebuggerTest):
    message_map: dict = {}

    ############ setup ############
    def _setup(self, probes: list[dict], request_path: str):
        self.initialize_weblog_remote_config()
        self.set_probes(probes)
        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=60):
            self.setup_failures = ["Probes did not reach INSTALLED status"]
            # Stop the test if the probes did not reach INSTALLED status since the probe won't exist
            # to send a snapshot.
            return

        self.send_weblog_request(request_path)
        self.wait_for_all_probes(statuses=["EMITTING"])
        self.wait_for_all_snapshots(timeout=60)

    ############ assert ############
    def _assert(self, expected_response: int):
        self.collect()

        self.assert_setup_ok()

        assert len(self.probe_ids) > 0, (
            "Expected probes to be created for validation. "
            "Check if the language supports the required probe type for this test."
        )

        self.assert_rc_state_not_error()
        self.assert_all_probes_are_emitting()
        self.assert_all_weblog_responses_ok(expected_response)
        self._validate_expression_language_messages(self.message_map)

    def _validate_expression_language_messages(self, expected_message_map: dict):
        not_found_ids = set(self.probe_ids)
        error_messages = []

        for probe_id, snapshots in self.probe_snapshots.items():
            for base in snapshots:
                snapshot = base.get("debugger", {}).get("snapshot") or base["debugger.snapshot"]
                assert snapshot

                if probe_id in expected_message_map:
                    not_found_ids.remove(probe_id)

                    if not re.search(expected_message_map[probe_id], base["message"]):
                        error_messages.append(
                            f"Message for probe id {probe_id} is wrong. \n Expected: {expected_message_map[probe_id]}. \n Found: {base['message']}."
                        )

                        evaluation_errors = snapshot.get("evaluationErrors", [])
                        for error in evaluation_errors:
                            error_messages.append(
                                f" Evaluation error in probe id {probe_id}: {error['expr']} - {error['message']}\n"
                            )

        not_found_list = "\n".join(not_found_ids)
        assert not error_messages, "Errors occurred during validation:\n" + "\n".join(error_messages)
        assert not not_found_ids, f"The following probes were not found:\n{not_found_list}"

    ############ test ############
    ############ access variables ############
    def setup_expression_language_access_variables(self):
        language, method = self.get_tracer()["language"], "Expression"
        message_map, probes = self._create_expression_probes(
            method_name=method,
            expressions=[
                ["Accessing input", "asd", Dsl("ref", "inputValue")],
                ["Accessing local", 3, Dsl("ref", "localValue")],
                [
                    "Accessing complex object int",
                    1,
                    Dsl("getmember", [Dsl("ref", "testStruct"), "IntValue"]),
                ],
                [
                    "Accessing complex object double",
                    1.1,
                    Dsl("getmember", [Dsl("ref", "testStruct"), "DoubleValue"]),
                ],
                [
                    "Accessing complex object string",
                    "one",
                    Dsl("getmember", [Dsl("ref", "testStruct"), "StringValue"]),
                ],
                [
                    "Accessing complex object bool",
                    "[Tt]rue",
                    Dsl("getmember", [Dsl("ref", "testStruct"), "BoolValue"]),
                ],
                [
                    "Accessing complex object collection first element",
                    "one",
                    Dsl(
                        "index",
                        [Dsl("getmember", [Dsl("ref", "testStruct"), "Collection"]), 0],
                    ),
                ],
                [
                    "Accessing complex object collection 'two' keyword",
                    2,
                    Dsl(
                        "index",
                        [
                            Dsl("getmember", [Dsl("ref", "testStruct"), "Dictionary"]),
                            "two",
                        ],
                    ),
                ],
            ],
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression?inputValue=asd")

    def test_expression_language_access_variables(self):
        self._assert(expected_response=200)

    def setup_expression_language_contextual_variables(self):
        message_map, probes = self._create_expression_probes(
            method_name="Expression",
            expressions=[
                ["Accessing return", ".*Great success number 3", Dsl("ref", "@return")],
                ["Accessing duration", r"\d+(\.\d+)?", Dsl("ref", "@duration")],
            ],
            # We only capture @return and @duration in the context of a method probe.
            lines=[],
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression?inputValue=asd")

    def test_expression_language_contextual_variables(self):
        self._assert(expected_response=200)

    ############ access exception ############
    def setup_expression_language_access_exception(self):
        language, method = self.get_tracer()["language"], "ExpressionException"
        if self.get_tracer()["language"] == "ruby":
            # Ruby does not include exception message into serialized payloads
            # at the moment (this requires writing serialization code in C).
            expected_message = ".*RuntimeError"
        else:
            expected_message = ".*Hello from exception"
        message_map, probes = self._create_expression_probes(
            method_name=method,
            expressions=[["Accessing exception", expected_message, Dsl("ref", "@exception")]],
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/exception")

    def test_expression_language_access_exception(self):
        self._assert(expected_response=500)

    ############ comparison operators ############
    def setup_expression_language_comparison_operators(self):
        language, method = self.get_tracer()["language"], "ExpressionOperators"
        message_map, probes = self._create_expression_probes(
            method_name=method,
            expressions=[
                ["intValue eq 5", True, Dsl("eq", [Dsl("ref", "intValue"), 5])],
                ["intValue ne 0", True, Dsl("ne", [Dsl("ref", "intValue"), 0])],
                ["intValue lt 10", True, Dsl("lt", [Dsl("ref", "intValue"), 10])],
                ["intValue gt 0", True, Dsl("gt", [Dsl("ref", "intValue"), 0])],
                ["intValue le 10", True, Dsl("le", [Dsl("ref", "intValue"), 10])],
                ["intValue le 5", True, Dsl("le", [Dsl("ref", "intValue"), 5])],
                ["intValue ge 0", True, Dsl("ge", [Dsl("ref", "intValue"), 0])],
                ["intValue ge 5", True, Dsl("ge", [Dsl("ref", "intValue"), 5])],
                ["intValue eq 0", False, Dsl("eq", [Dsl("ref", "intValue"), 0])],
                ["intValue lt 0", False, Dsl("lt", [Dsl("ref", "intValue"), 0])],
                ["intValue gt 10", False, Dsl("gt", [Dsl("ref", "intValue"), 10])],
                ["intValue ne 5", False, Dsl("ne", [Dsl("ref", "intValue"), 5])],
                ["intValue le 0", False, Dsl("le", [Dsl("ref", "intValue"), 0])],
                ["intValue ge 10", False, Dsl("ge", [Dsl("ref", "intValue"), 10])],
                ["floatValue ne 0", True, Dsl("ne", [Dsl("ref", "floatValue"), 0])],
                ["floatValue ne 0.1", True, Dsl("ne", [Dsl("ref", "floatValue"), 0.1])],
                ["floatValue lt 10", True, Dsl("lt", [Dsl("ref", "floatValue"), 10])],
                [
                    "floatValue lt 10.10",
                    True,
                    Dsl("lt", [Dsl("ref", "floatValue"), 10.10]),
                ],
                ["floatValue gt 0", True, Dsl("gt", [Dsl("ref", "floatValue"), 0])],
                ["floatValue gt 0.0", True, Dsl("gt", [Dsl("ref", "floatValue"), 0.0])],
                ["floatValue le 5", True, Dsl("le", [Dsl("ref", "floatValue"), 5])],
                ["floatValue le 5.5", True, Dsl("le", [Dsl("ref", "floatValue"), 5.5])],
                ["floatValue ge 0", True, Dsl("ge", [Dsl("ref", "floatValue"), 0])],
                ["floatValue ge 0.0", True, Dsl("ge", [Dsl("ref", "floatValue"), 0.0])],
                ["floatValue eq 0", False, Dsl("eq", [Dsl("ref", "floatValue"), 0])],
                [
                    "floatValue eq 0.0",
                    False,
                    Dsl("eq", [Dsl("ref", "floatValue"), 0.0]),
                ],
                ["floatValue lt 0", False, Dsl("lt", [Dsl("ref", "floatValue"), 0])],
                [
                    "floatValue lt 0.0",
                    False,
                    Dsl("lt", [Dsl("ref", "floatValue"), 0.0]),
                ],
                ["floatValue gt 10", False, Dsl("gt", [Dsl("ref", "floatValue"), 10])],
                [
                    "floatValue gt 10.10",
                    False,
                    Dsl("gt", [Dsl("ref", "floatValue"), 10.10]),
                ],
                ["floatValue le 0", False, Dsl("le", [Dsl("ref", "floatValue"), 0])],
                [
                    "floatValue le 0.0",
                    False,
                    Dsl("le", [Dsl("ref", "floatValue"), 0.0]),
                ],
                ["floatValue ge 10", False, Dsl("ge", [Dsl("ref", "floatValue"), 10])],
                [
                    "floatValue ge 10.10",
                    False,
                    Dsl("ge", [Dsl("ref", "floatValue"), 10.10]),
                ],
                ["strValue eq haha", True, Dsl("eq", [Dsl("ref", "strValue"), "haha"])],
                ["strValue ne hoho", True, Dsl("ne", [Dsl("ref", "strValue"), "hoho"])],
                ["strValue lt z", True, Dsl("lt", [Dsl("ref", "strValue"), "z"])],
                ["strValue gt a", True, Dsl("gt", [Dsl("ref", "strValue"), "a"])],
                ["strValue le haha", True, Dsl("le", [Dsl("ref", "strValue"), "haha"])],
                ["strValue le z", True, Dsl("le", [Dsl("ref", "strValue"), "z"])],
                ["strValue ge a", True, Dsl("ge", [Dsl("ref", "strValue"), "a"])],
                ["strValue ge haha", True, Dsl("ge", [Dsl("ref", "strValue"), "haha"])],
                [
                    "strValue eq hoho",
                    False,
                    Dsl("eq", [Dsl("ref", "strValue"), "hoho"]),
                ],
                ["strValue lt a", False, Dsl("lt", [Dsl("ref", "strValue"), "a"])],
                ["strValue gt z", False, Dsl("gt", [Dsl("ref", "strValue"), "z"])],
                ["strValue le a", False, Dsl("le", [Dsl("ref", "strValue"), "a"])],
                ["strValue ge z", False, Dsl("ge", [Dsl("ref", "strValue"), "z"])],
            ],
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(
            probes,
            "/debugger/expression/operators?intValue=5&floatValue=3.14&strValue=haha",
        )

    def test_expression_language_comparison_operators(self):
        self._assert(expected_response=200)

    ############ instance of ############
    def setup_expression_language_instance_of(self):
        language, method = self.get_tracer()["language"], "ExpressionOperators"
        message_map, probes = self._create_expression_probes(
            method_name=method,
            expressions=[
                [
                    "intValue instanceof int",
                    True,
                    Dsl("instanceof", [Dsl("ref", "intValue"), self._get_type("int")]),
                ],
                [
                    "floatValue instanceof float",
                    True,
                    Dsl(
                        "instanceof",
                        [Dsl("ref", "floatValue"), self._get_type("float")],
                    ),
                ],
                [
                    "strValue instanceof string",
                    True,
                    Dsl("instanceof", [Dsl("ref", "strValue"), self._get_type("string")]),
                ],
                [
                    "pii instanceof pii",
                    True,
                    Dsl("instanceof", [Dsl("ref", "pii"), self._get_type("pii")]),
                ],
                [
                    "pii instanceof pii base",
                    True,
                    Dsl("instanceof", [Dsl("ref", "pii"), self._get_type("pii")]),
                ],
                [
                    "intValue instanceof float",
                    self.get_tracer()["language"] == "nodejs",
                    Dsl("instanceof", [Dsl("ref", "intValue"), self._get_type("float")]),
                ],
                [
                    "floatValue instanceof int",
                    self.get_tracer()["language"] == "nodejs",
                    Dsl("instanceof", [Dsl("ref", "floatValue"), self._get_type("int")]),
                ],
                [
                    "strValue instanceof float",
                    False,
                    Dsl("instanceof", [Dsl("ref", "strValue"), self._get_type("float")]),
                ],
                [
                    "pii instanceof string",
                    False,
                    Dsl("instanceof", [Dsl("ref", "pii"), self._get_type("string")]),
                ],
            ],
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(
            probes,
            "/debugger/expression/operators?intValue=5&floatValue=3.14&strValue=haha",
        )

    def test_expression_language_instance_of(self):
        self._assert(expected_response=200)

    ############ logical operators ############
    def setup_expression_language_logical_operators(self):
        language, method = self.get_tracer()["language"], "ExpressionOperators"
        message_map, probes = self._create_expression_probes(
            method_name=method,
            expressions=[
                [
                    "intValue eq 5 and strValue ne 5",
                    True,
                    Dsl(
                        "and",
                        [
                            Dsl("eq", [Dsl("ref", "intValue"), 5]),
                            Dsl("ne", [Dsl("ref", "strValue"), "5"]),
                        ],
                    ),
                ],
                [
                    "intValue eq 1 or strValue eq haha",
                    True,
                    Dsl(
                        "or",
                        [
                            Dsl("eq", [Dsl("ref", "intValue"), 1]),
                            Dsl("eq", [Dsl("ref", "strValue"), "haha"]),
                        ],
                    ),
                ],
                [
                    "not intValue ne 10",
                    True,
                    Dsl("not", Dsl("ne", [Dsl("ref", "intValue"), 5])),
                ],
                [
                    "intValue eq 5 and strValue ne haha",
                    False,
                    Dsl(
                        "and",
                        [
                            Dsl("eq", [Dsl("ref", "intValue"), 5]),
                            Dsl("ne", [Dsl("ref", "strValue"), "haha"]),
                        ],
                    ),
                ],
                [
                    "intValue eq 1 or strValue eq hoho",
                    False,
                    Dsl(
                        "or",
                        [
                            Dsl("eq", [Dsl("ref", "intValue"), 1]),
                            Dsl("eq", [Dsl("ref", "strValue"), "hoho"]),
                        ],
                    ),
                ],
                [
                    "not intValue eq 10",
                    False,
                    Dsl("not", Dsl("eq", [Dsl("ref", "intValue"), 5])),
                ],
            ],
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(
            probes,
            "/debugger/expression/operators?intValue=5&floatValue=3.14&strValue=haha",
        )

    def test_expression_language_logical_operators(self):
        self._assert(expected_response=200)


    ############ helpers ############
    def _get_type(self, value_type: str):
        return get_type(self.get_tracer()["language"], value_type)

    def _create_expression_probes(self, method_name: str, expressions: list[list], lines: list | tuple = ()):
        return create_expression_probes(
            self.get_tracer()["language"],
            method_name=method_name,
            expressions=expressions,
            lines=lines,
        )
