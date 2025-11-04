# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger
import re
import json
from utils import scenarios, features, bug, missing_feature, context


@features.debugger_expression_language
@scenarios.debugger_expression_language
class Test_Debugger_Expression_Language(debugger.BaseDebuggerTest):
    message_map: dict = {}

    ############ setup ############
    def _setup(self, probes: list[dict], request_path: str):
        self.set_probes(probes)
        self.send_rc_probes()
        self.wait_for_all_probes(statuses=["INSTALLED"])
        self.send_weblog_request(request_path)
        self.wait_for_all_probes(statuses=["EMITTING"])
        self.wait_for_snapshot_received()

    ############ assert ############
    def _assert(self, expected_response: int):
        self.collect()

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
                ["Accessing complex object int", 1, Dsl("getmember", [Dsl("ref", "testStruct"), "IntValue"])],
                ["Accessing complex object double", 1.1, Dsl("getmember", [Dsl("ref", "testStruct"), "DoubleValue"])],
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
                    Dsl("index", [Dsl("getmember", [Dsl("ref", "testStruct"), "Collection"]), 0]),
                ],
                [
                    "Accessing complex object collection 'two' keyword",
                    2,
                    Dsl("index", [Dsl("getmember", [Dsl("ref", "testStruct"), "Dictionary"]), "two"]),
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

    @missing_feature(library="nodejs", reason="Not yet implemented")
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

    @missing_feature(library="nodejs", reason="Not yet implemented")
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
                ["floatValue lt 10.10", True, Dsl("lt", [Dsl("ref", "floatValue"), 10.10])],
                ["floatValue gt 0", True, Dsl("gt", [Dsl("ref", "floatValue"), 0])],
                ["floatValue gt 0.0", True, Dsl("gt", [Dsl("ref", "floatValue"), 0.0])],
                ["floatValue le 5", True, Dsl("le", [Dsl("ref", "floatValue"), 5])],
                ["floatValue le 5.5", True, Dsl("le", [Dsl("ref", "floatValue"), 5.5])],
                ["floatValue ge 0", True, Dsl("ge", [Dsl("ref", "floatValue"), 0])],
                ["floatValue ge 0.0", True, Dsl("ge", [Dsl("ref", "floatValue"), 0.0])],
                ["floatValue eq 0", False, Dsl("eq", [Dsl("ref", "floatValue"), 0])],
                ["floatValue eq 0.0", False, Dsl("eq", [Dsl("ref", "floatValue"), 0.0])],
                ["floatValue lt 0", False, Dsl("lt", [Dsl("ref", "floatValue"), 0])],
                ["floatValue lt 0.0", False, Dsl("lt", [Dsl("ref", "floatValue"), 0.0])],
                ["floatValue gt 10", False, Dsl("gt", [Dsl("ref", "floatValue"), 10])],
                ["floatValue gt 10.10", False, Dsl("gt", [Dsl("ref", "floatValue"), 10.10])],
                ["floatValue le 0", False, Dsl("le", [Dsl("ref", "floatValue"), 0])],
                ["floatValue le 0.0", False, Dsl("le", [Dsl("ref", "floatValue"), 0.0])],
                ["floatValue ge 10", False, Dsl("ge", [Dsl("ref", "floatValue"), 10])],
                ["floatValue ge 10.10", False, Dsl("ge", [Dsl("ref", "floatValue"), 10.10])],
                ["strValue eq haha", True, Dsl("eq", [Dsl("ref", "strValue"), "haha"])],
                ["strValue ne hoho", True, Dsl("ne", [Dsl("ref", "strValue"), "hoho"])],
                ["strValue lt z", True, Dsl("lt", [Dsl("ref", "strValue"), "z"])],
                ["strValue gt a", True, Dsl("gt", [Dsl("ref", "strValue"), "a"])],
                ["strValue le haha", True, Dsl("le", [Dsl("ref", "strValue"), "haha"])],
                ["strValue le z", True, Dsl("le", [Dsl("ref", "strValue"), "z"])],
                ["strValue ge a", True, Dsl("ge", [Dsl("ref", "strValue"), "a"])],
                ["strValue ge haha", True, Dsl("ge", [Dsl("ref", "strValue"), "haha"])],
                ["strValue eq hoho", False, Dsl("eq", [Dsl("ref", "strValue"), "hoho"])],
                ["strValue lt a", False, Dsl("lt", [Dsl("ref", "strValue"), "a"])],
                ["strValue gt z", False, Dsl("gt", [Dsl("ref", "strValue"), "z"])],
                ["strValue le a", False, Dsl("le", [Dsl("ref", "strValue"), "a"])],
                ["strValue ge z", False, Dsl("ge", [Dsl("ref", "strValue"), "z"])],
            ],
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/operators?intValue=5&floatValue=3.14&strValue=haha")

    def test_expression_language_comparison_operators(self):
        self._assert(expected_response=200)

    ############ instance of ############
    def setup_expression_language_instance_of(self):
        language, method = self.get_tracer()["language"], "ExpressionOperators"
        message_map, probes = self._create_expression_probes(
            method_name=method,
            expressions=[
                ["intValue instanceof int", True, Dsl("instanceof", [Dsl("ref", "intValue"), self._get_type("int")])],
                [
                    "floatValue instanceof float",
                    True,
                    Dsl("instanceof", [Dsl("ref", "floatValue"), self._get_type("float")]),
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
                ["pii instanceof string", False, Dsl("instanceof", [Dsl("ref", "pii"), self._get_type("string")])],
            ],
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/operators?intValue=5&floatValue=3.14&strValue=haha")

    @bug(library="dotnet", reason="DEBUG-2530")
    @bug(library="nodejs", weblog_variant="express4-typescript", reason="DEBUG-3715")
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
                    Dsl("and", [Dsl("eq", [Dsl("ref", "intValue"), 5]), Dsl("ne", [Dsl("ref", "strValue"), "5"])]),
                ],
                [
                    "intValue eq 1 or strValue eq haha",
                    True,
                    Dsl("or", [Dsl("eq", [Dsl("ref", "intValue"), 1]), Dsl("eq", [Dsl("ref", "strValue"), "haha"])]),
                ],
                ["not intValue ne 10", True, Dsl("not", Dsl("ne", [Dsl("ref", "intValue"), 5]))],
                [
                    "intValue eq 5 and strValue ne haha",
                    False,
                    Dsl("and", [Dsl("eq", [Dsl("ref", "intValue"), 5]), Dsl("ne", [Dsl("ref", "strValue"), "haha"])]),
                ],
                [
                    "intValue eq 1 or strValue eq hoho",
                    False,
                    Dsl("or", [Dsl("eq", [Dsl("ref", "intValue"), 1]), Dsl("eq", [Dsl("ref", "strValue"), "hoho"])]),
                ],
                ["not intValue eq 10", False, Dsl("not", Dsl("eq", [Dsl("ref", "intValue"), 5]))],
            ],
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/operators?intValue=5&floatValue=3.14&strValue=haha")

    @bug(context.library == "dotnet@3.5.0", reason="DEBUG-3115")
    def test_expression_language_logical_operators(self):
        self._assert(expected_response=200)

    ############ string operations ############
    def setup_expression_language_string_operations(self):
        language, method = self.get_tracer()["language"], "StringOperations"
        message_map, probes = self._create_expression_probes(
            method_name=method,
            expressions=[
                ##### isempty
                ["strValue isEmpty", False, Dsl("isEmpty", Dsl("ref", "strValue"))],
                ["emptyString isEmpty", True, Dsl("isEmpty", Dsl("ref", "emptyString"))],
                ##### len
                ["strValue len", 14, Dsl("len", Dsl("ref", "strValue"))],
                ["emptyString len", 0, Dsl("len", Dsl("ref", "emptyString"))],
                ##### substring
                ["strValue substring 0 5", "veryl", Dsl("substring", [Dsl("ref", "strValue"), 0, 5])],
                ["strValue substring 5 10", "ongst", Dsl("substring", [Dsl("ref", "strValue"), 5, 10])],
                ["strValue substring 0 0", "", Dsl("substring", [Dsl("ref", "strValue"), 0, 0])],
                ["emptyString substring 0 0", "", Dsl("substring", [Dsl("ref", "emptyString"), 0, 0])],
                ##### startsWith
                ["strValue startsWith very", True, Dsl("startsWith", [Dsl("ref", "strValue"), "very"])],
                ["strValue startsWith foo", False, Dsl("startsWith", [Dsl("ref", "strValue"), "foo"])],
                ["emptyString startsWith empty", True, Dsl("startsWith", [Dsl("ref", "emptyString"), ""])],
                ["emptyString startsWith some", False, Dsl("startsWith", [Dsl("ref", "emptyString"), "some"])],
                ##### endsWith
                ["strValue endsWith ring", True, Dsl("endsWith", [Dsl("ref", "strValue"), "ring"])],
                ["strValue endsWith foo", False, Dsl("endsWith", [Dsl("ref", "strValue"), "foo"])],
                ["emptyString endsWith empty", True, Dsl("endsWith", [Dsl("ref", "emptyString"), ""])],
                ["emptyString endsWith some", False, Dsl("endsWith", [Dsl("ref", "emptyString"), "foo"])],
                ##### contains
                ["strValue contains str", True, Dsl("contains", [Dsl("ref", "strValue"), "str"])],
                ["strValue contains STR", False, Dsl("contains", [Dsl("ref", "strValue"), "STR"])],
                ["emptyString contains empty", True, Dsl("contains", [Dsl("ref", "emptyString"), ""])],
                ["emptyString contains some", False, Dsl("contains", [Dsl("ref", "emptyString"), "foo"])],
                ##### matches
                ["strValue matches regex", True, Dsl("matches", [Dsl("ref", "strValue"), "^v.*g$"])],
                ["strValue matches STR", False, Dsl("matches", [Dsl("ref", "strValue"), "foo"])],
                ["emptyString matches empty", True, Dsl("matches", [Dsl("ref", "emptyString"), ""])],
                ["emptyString matches some", False, Dsl("matches", [Dsl("ref", "emptyString"), "foo"])],
            ],
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/strings?strValue=verylongstring")

    @bug(library="dotnet", reason="DEBUG-2560")
    def test_expression_language_string_operations(self):
        self._assert(expected_response=200)

    ############ collection operations ############
    ## at the app there are 3 types of collections are created - array, list and hash.
    ## the number at the end of variable means the length of the collection
    ## all collection are filled with incremented number values (e.g at the [0] = 0; [1] = 1)

    def setup_expression_language_collection_operations(self):
        language, method = self.get_tracer()["language"], "CollectionOperations"
        message_map, probes = self._create_expression_probes(
            method_name=method,
            expressions=[
                ##### len
                ["Array0 len", 0, Dsl("len", Dsl("ref", "a0"))],
                ["Array1 len", 1, Dsl("len", Dsl("ref", "a1"))],
                ["Array5 len", 5, Dsl("len", Dsl("ref", "a5"))],
                ["List0 len", 0, Dsl("len", Dsl("ref", "l0"))],
                ["List1 len", 1, Dsl("len", Dsl("ref", "l1"))],
                ["List5 len", 5, Dsl("len", Dsl("ref", "l5"))],
                ##### index
                # TODO: It's not a good test to check that index x contains the value x. Instead it should test that index x contains y
                ["Array5 index 4", 4, Dsl("index", [Dsl("ref", "a5"), 4])],
                ["List5 index 4", 4, Dsl("index", [Dsl("ref", "l5"), 4])],
                ##### any
                ["Array0 any gt 1", False, Dsl("any", [Dsl("ref", "a0"), Dsl("gt", [Dsl("ref", "@it"), 1])])],
                ["Array1 any gt 1", False, Dsl("any", [Dsl("ref", "a1"), Dsl("gt", [Dsl("ref", "@it"), 1])])],
                ["Array5 any gt 1", True, Dsl("any", [Dsl("ref", "a5"), Dsl("gt", [Dsl("ref", "@it"), 1])])],
                ["List0 any gt 1", False, Dsl("any", [Dsl("ref", "l0"), Dsl("gt", [Dsl("ref", "@it"), 1])])],
                ["List1 any gt 1", False, Dsl("any", [Dsl("ref", "l1"), Dsl("gt", [Dsl("ref", "@it"), 1])])],
                ["List5 any gt 1", True, Dsl("any", [Dsl("ref", "l5"), Dsl("gt", [Dsl("ref", "@it"), 1])])],
                ##### all
                ["Array0 all ge 0", True, Dsl("all", [Dsl("ref", "a0"), Dsl("ge", [Dsl("ref", "@it"), 0])])],
                ["Array1 all ge 0", True, Dsl("all", [Dsl("ref", "a1"), Dsl("ge", [Dsl("ref", "@it"), 0])])],
                ["Array5 all ge 1", False, Dsl("all", [Dsl("ref", "a5"), Dsl("ge", [Dsl("ref", "@it"), 1])])],
                ["List0 all ge 0", True, Dsl("all", [Dsl("ref", "l0"), Dsl("ge", [Dsl("ref", "@it"), 0])])],
                ["List1 all ge 0", True, Dsl("all", [Dsl("ref", "l1"), Dsl("ge", [Dsl("ref", "@it"), 0])])],
                ["List5 all ge 1", False, Dsl("all", [Dsl("ref", "l5"), Dsl("ge", [Dsl("ref", "@it"), 1])])],
                ##### filter
                [
                    "Array0 len filter lt 2",
                    0,
                    Dsl("len", Dsl("filter", [Dsl("ref", "a0"), Dsl("lt", [Dsl("ref", "@it"), 2])])),
                ],
                [
                    "Array1 len filter lt 2",
                    1,
                    Dsl("len", Dsl("filter", [Dsl("ref", "a1"), Dsl("lt", [Dsl("ref", "@it"), 2])])),
                ],
                [
                    "Array5 len filter lt 2",
                    2,
                    Dsl("len", Dsl("filter", [Dsl("ref", "a5"), Dsl("lt", [Dsl("ref", "@it"), 2])])),
                ],
                [
                    "List0 len filter lt 2",
                    0,
                    Dsl("len", Dsl("filter", [Dsl("ref", "l0"), Dsl("lt", [Dsl("ref", "@it"), 2])])),
                ],
                [
                    "List1 len filter lt 2",
                    1,
                    Dsl("len", Dsl("filter", [Dsl("ref", "l1"), Dsl("lt", [Dsl("ref", "@it"), 2])])),
                ],
                [
                    "List5 len filter lt 2",
                    2,
                    Dsl("len", Dsl("filter", [Dsl("ref", "l5"), Dsl("lt", [Dsl("ref", "@it"), 2])])),
                ],
            ],
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/collections")

    def test_expression_language_collection_operations(self):
        self._assert(expected_response=200)

    def setup_expression_language_hash_operations(self):
        language, method = self.get_tracer()["language"], "CollectionOperations"
        if self.get_tracer()["language"] == "dotnet":
            get_hash_value = Dsl("getmember", [Dsl("ref", "@it"), "Value"])
        elif self.get_tracer()["language"] in ["nodejs", "ruby"]:
            get_hash_value = Dsl("ref", "@value")
        else:
            get_hash_value = Dsl("getmember", [Dsl("ref", "@it"), "value"])

        message_map, probes = self._create_expression_probes(
            method_name=method,
            expressions=[
                ## at the app there are 3 types of collections are created - array, list and hash.
                ## the number at the end of variable means the length of the collection
                ## all collection are filled with incremented number values (e.g at the [0] = 0; [1] = 1)
                #### len
                ["Hash0 len", 0, Dsl("len", Dsl("ref", "h0"))],
                ["Hash1 len", 1, Dsl("len", Dsl("ref", "h1"))],
                ["Hash5 len", 5, Dsl("len", Dsl("ref", "h5"))],
                ##### index
                ["Hash5 index 4", 4, Dsl("index", [Dsl("ref", "h5"), 4])],
                ##### any
                ["Hash0 any gt 1", False, Dsl("any", [Dsl("ref", "h0"), Dsl("gt", [get_hash_value, 1])])],
                ["Hash1 any gt 1", False, Dsl("any", [Dsl("ref", "h1"), Dsl("gt", [get_hash_value, 1])])],
                ["Hash5 any gt 1", True, Dsl("any", [Dsl("ref", "h5"), Dsl("gt", [get_hash_value, 1])])],
                ##### all
                ["Hash0 all ge 0", True, Dsl("all", [Dsl("ref", "h0"), Dsl("ge", [get_hash_value, 0])])],
                ["Hash1 all ge 0", True, Dsl("all", [Dsl("ref", "h1"), Dsl("ge", [get_hash_value, 0])])],
                ["Hash5 all ge 1", False, Dsl("all", [Dsl("ref", "h5"), Dsl("ge", [get_hash_value, 1])])],
                ##### filter
                [
                    "Hash0 len filter lt 2",
                    0,
                    Dsl("len", Dsl("filter", [Dsl("ref", "h0"), Dsl("lt", [get_hash_value, 2])])),
                ],
                [
                    "Hash1 len filter lt 2",
                    1,
                    Dsl("len", Dsl("filter", [Dsl("ref", "h1"), Dsl("lt", [get_hash_value, 2])])),
                ],
                [
                    "Hash5 len filter lt 2",
                    2,
                    Dsl("len", Dsl("filter", [Dsl("ref", "h5"), Dsl("lt", [get_hash_value, 2])])),
                ],
            ],
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/collections")

    @bug(library="dotnet", reason="DEBUG-2602")
    @missing_feature(library="python", reason="DEBUG-3240", force_skip=True)
    @missing_feature(context.library <= "ruby@2.22.0", reason="Hash length not implemented")
    def test_expression_language_hash_operations(self):
        self._assert(expected_response=200)

    ############ nulls ############
    def setup_expression_language_nulls_true(self):
        language, method = self.get_tracer()["language"], "Nulls"
        expressions = [["pii eq null", True, Dsl("eq", [Dsl("ref", "pii"), None])]]

        # In Node.js, numbers and strings cannot be null as they are not objects
        if language != "nodejs":
            expressions.extend(
                [
                    ["intValue eq null", True, Dsl("eq", [Dsl("ref", "intValue"), None])],
                    ["strValue eq null", True, Dsl("eq", [Dsl("ref", "strValue"), None])],
                ]
            )

        message_map, probes = self._create_expression_probes(
            method_name=method,
            expressions=expressions,
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/null")

    @bug(library="dotnet", reason="DEBUG-2618")
    def test_expression_language_nulls_true(self):
        self._assert(expected_response=200)

    def setup_expression_language_nulls_false(self):
        language, method = self.get_tracer()["language"], "Nulls"
        message_map, probes = self._create_expression_probes(
            method_name=method,
            expressions=[
                ["intValue eq null", False, Dsl("eq", [Dsl("ref", "intValue"), None])],
                ["strValue eq null", False, Dsl("eq", [Dsl("ref", "strValue"), None])],
                ["pii eq null", False, Dsl("eq", [Dsl("ref", "pii"), None])],
            ],
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/null?intValue=5&strValue=haha&boolValue=true")

    @bug(library="dotnet", reason="DEBUG-2618")
    def test_expression_language_nulls_false(self):
        self._assert(expected_response=200)

    ############ helpers ############
    def _get_type(self, value_type: str):
        instance_type = ""

        if self.get_tracer()["language"] == "dotnet":
            if value_type == "int":
                instance_type = "System.Int32"
            elif value_type == "float":
                instance_type = "System.Single"
            elif value_type == "string":
                instance_type = "System.String"
            elif value_type == "pii":
                instance_type = "weblog.Models.Debugger.Pii"
            elif value_type == "pii_base":
                instance_type = "weblog.Models.Debugger.PiiBase"
            else:
                instance_type = value_type
        elif self.get_tracer()["language"] == "java":
            if value_type == "int":
                instance_type = "java.lang.Integer"
            elif value_type == "float":
                instance_type = "java.lang.Float"
            elif value_type == "string":
                instance_type = "java.lang.String"
            elif value_type == "pii":
                instance_type = "com.datadoghq.system_tests.springboot.PiiBase"
            else:
                instance_type = value_type
        elif self.get_tracer()["language"] == "python":
            if value_type == "int":
                instance_type = "int"
            elif value_type == "float":
                instance_type = "float"
            elif value_type == "string":
                instance_type = "str"
            elif value_type == "pii":
                instance_type = "debugger.pii.Pii"
            else:
                instance_type = value_type
        elif self.get_tracer()["language"] == "ruby":
            if value_type == "int":
                instance_type = "Integer"
            elif value_type == "float":
                instance_type = "Float"
            elif value_type == "string":
                instance_type = "String"
            elif value_type == "pii":
                instance_type = "Pii"
            else:
                instance_type = value_type
        elif self.get_tracer()["language"] == "nodejs":
            if value_type in ("int", "float"):
                instance_type = "number"
            elif value_type == "string":
                instance_type = "string"
            elif value_type == "pii":
                instance_type = "Pii"
            else:
                instance_type = value_type
        else:
            instance_type = value_type

        return instance_type

    def _create_expression_probes(self, method_name: str, expressions: list[list], lines: list | tuple = ()):
        probes = []
        expected_message_map = {}
        prob_types = []
        # Method probes do not capture locals in Ruby, therefore in Ruby
        # we set line probes.
        # The exception is the test case testing @exception capture
        # which requires a method probe (and this case does not capture
        # local variables).
        if self.get_tracer()["language"] == "ruby":
            if method_name == "Expression" and not lines:
                prob_types.append("method")
                method_name = "expression"
            elif method_name == "ExpressionException":
                prob_types.append("method")
                method_name = "expression_exception"
            else:
                prob_types.append("line")
        elif self.get_tracer()["language"] != "nodejs":  # Method probes are not supported in Node.js
            prob_types.append("method")
        if len(lines) > 0 and "line" not in prob_types:
            prob_types.append("line")

        for probe_type in prob_types:
            for expression in expressions:
                expression_to_test, expected_result, dsl = expression
                message = f"Expression to test: '{expression_to_test}'. Result is: "

                if isinstance(expected_result, bool):
                    expected_result = "[Tt]rue" if expected_result else "[Ff]alse"
                elif isinstance(expected_result, str) and expected_result and expected_result != "":
                    expected_result = f"[']?{expected_result}[']?"
                else:
                    expected_result = str(expected_result)

                probe = debugger.read_probes("expression_probe_base")[0]
                probe["id"] = debugger.generate_probe_id("log")
                if probe_type == "method":
                    probe["where"]["methodName"] = method_name
                if probe_type == "line":
                    del probe["where"]["methodName"]
                    probe["where"]["lines"] = lines
                    probe["where"]["sourceFile"] = "ACTUAL_SOURCE_FILE"
                    probe["where"]["typeName"] = None

                probe["segments"] = Segment().add_str(message).add_dsl(dsl).to_dict()
                probes.append(probe)

                expected_message_map[probe["id"]] = message + expected_result

        return expected_message_map, probes


class Segment:
    def __init__(self):
        self.segments = []

    def add_str(self, string: str):
        self.segments.append({"str": string})
        return self

    def add_dsl(self, dsl_creator: "Segment"):
        self.segments.append({"dsl": "", "json": dsl_creator.to_dict()})
        return self

    def to_dict(self) -> list:
        return self.segments

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class Dsl:
    def __init__(self, operator: str, value: "list|str|Dsl"):
        self.data = {}

        if isinstance(value, Dsl):
            self.data[operator] = value.to_dict()
        elif isinstance(value, list):
            self.data[operator] = [v.to_dict() if isinstance(v, Dsl) else v for v in value]
        else:
            self.data[operator] = value

    def to_dict(self):
        return self.data

    def to_json(self):
        return json.dumps(self.to_dict())
