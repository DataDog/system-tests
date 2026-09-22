# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import re

import tests.debugger.utils as debugger
from tests.debugger.utils import Dsl, Segment, create_expression_probes, get_type
from utils import scenarios, features, slow


@features.debugger_expression_language_2
@scenarios.debugger_expression_language_2
@slow
class Test_Debugger_Expression_Language_2(debugger.BaseDebuggerTest):
    message_map: dict = {}

    ############ setup ############
    def _setup(self, probes: list[dict], request_path: str):
        self.initialize_weblog_remote_config()
        self.set_probes(probes)
        self.send_rc_probes()
        if not self.wait_for_all_probes(statuses=["INSTALLED"], timeout=60):
            self.setup_failures = ["Probes did not reach INSTALLED status"]
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

    ############ string operations ############
    def setup_expression_language_string_operations(self):
        language, method = self.get_tracer()["language"], "StringOperations"
        message_map, probes = self._create_expression_probes(
            method_name=method,
            expressions=[
                ##### isempty
                ["strValue isEmpty", False, Dsl("isEmpty", Dsl("ref", "strValue"))],
                [
                    "emptyString isEmpty",
                    True,
                    Dsl("isEmpty", Dsl("ref", "emptyString")),
                ],
                ##### len
                ["strValue len", 14, Dsl("len", Dsl("ref", "strValue"))],
                ["emptyString len", 0, Dsl("len", Dsl("ref", "emptyString"))],
                ##### substring
                [
                    "strValue substring 0 5",
                    "veryl",
                    Dsl("substring", [Dsl("ref", "strValue"), 0, 5]),
                ],
                [
                    "strValue substring 5 10",
                    "ongst",
                    Dsl("substring", [Dsl("ref", "strValue"), 5, 10]),
                ],
                [
                    "strValue substring 0 0",
                    "",
                    Dsl("substring", [Dsl("ref", "strValue"), 0, 0]),
                ],
                [
                    "emptyString substring 0 0",
                    "",
                    Dsl("substring", [Dsl("ref", "emptyString"), 0, 0]),
                ],
                ##### startsWith
                [
                    "strValue startsWith very",
                    True,
                    Dsl("startsWith", [Dsl("ref", "strValue"), "very"]),
                ],
                [
                    "strValue startsWith foo",
                    False,
                    Dsl("startsWith", [Dsl("ref", "strValue"), "foo"]),
                ],
                [
                    "emptyString startsWith empty",
                    True,
                    Dsl("startsWith", [Dsl("ref", "emptyString"), ""]),
                ],
                [
                    "emptyString startsWith some",
                    False,
                    Dsl("startsWith", [Dsl("ref", "emptyString"), "some"]),
                ],
                ##### endsWith
                [
                    "strValue endsWith ring",
                    True,
                    Dsl("endsWith", [Dsl("ref", "strValue"), "ring"]),
                ],
                [
                    "strValue endsWith foo",
                    False,
                    Dsl("endsWith", [Dsl("ref", "strValue"), "foo"]),
                ],
                [
                    "emptyString endsWith empty",
                    True,
                    Dsl("endsWith", [Dsl("ref", "emptyString"), ""]),
                ],
                [
                    "emptyString endsWith some",
                    False,
                    Dsl("endsWith", [Dsl("ref", "emptyString"), "foo"]),
                ],
                ##### contains
                [
                    "strValue contains str",
                    True,
                    Dsl("contains", [Dsl("ref", "strValue"), "str"]),
                ],
                [
                    "strValue contains STR",
                    False,
                    Dsl("contains", [Dsl("ref", "strValue"), "STR"]),
                ],
                [
                    "emptyString contains empty",
                    True,
                    Dsl("contains", [Dsl("ref", "emptyString"), ""]),
                ],
                [
                    "emptyString contains some",
                    False,
                    Dsl("contains", [Dsl("ref", "emptyString"), "foo"]),
                ],
                ##### matches
                [
                    "strValue matches regex",
                    True,
                    Dsl("matches", [Dsl("ref", "strValue"), "^v.*g$"]),
                ],
                [
                    "strValue matches STR",
                    False,
                    Dsl("matches", [Dsl("ref", "strValue"), "foo"]),
                ],
                [
                    "emptyString matches empty",
                    True,
                    Dsl("matches", [Dsl("ref", "emptyString"), ""]),
                ],
                [
                    "emptyString matches some",
                    False,
                    Dsl("matches", [Dsl("ref", "emptyString"), "foo"]),
                ],
            ],
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/strings?strValue=verylongstring")

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
                [
                    "Array0 any gt 1",
                    False,
                    Dsl("any", [Dsl("ref", "a0"), Dsl("gt", [Dsl("ref", "@it"), 1])]),
                ],
                [
                    "Array1 any gt 1",
                    False,
                    Dsl("any", [Dsl("ref", "a1"), Dsl("gt", [Dsl("ref", "@it"), 1])]),
                ],
                [
                    "Array5 any gt 1",
                    True,
                    Dsl("any", [Dsl("ref", "a5"), Dsl("gt", [Dsl("ref", "@it"), 1])]),
                ],
                [
                    "List0 any gt 1",
                    False,
                    Dsl("any", [Dsl("ref", "l0"), Dsl("gt", [Dsl("ref", "@it"), 1])]),
                ],
                [
                    "List1 any gt 1",
                    False,
                    Dsl("any", [Dsl("ref", "l1"), Dsl("gt", [Dsl("ref", "@it"), 1])]),
                ],
                [
                    "List5 any gt 1",
                    True,
                    Dsl("any", [Dsl("ref", "l5"), Dsl("gt", [Dsl("ref", "@it"), 1])]),
                ],
                ##### all
                [
                    "Array0 all ge 0",
                    True,
                    Dsl("all", [Dsl("ref", "a0"), Dsl("ge", [Dsl("ref", "@it"), 0])]),
                ],
                [
                    "Array1 all ge 0",
                    True,
                    Dsl("all", [Dsl("ref", "a1"), Dsl("ge", [Dsl("ref", "@it"), 0])]),
                ],
                [
                    "Array5 all ge 1",
                    False,
                    Dsl("all", [Dsl("ref", "a5"), Dsl("ge", [Dsl("ref", "@it"), 1])]),
                ],
                [
                    "List0 all ge 0",
                    True,
                    Dsl("all", [Dsl("ref", "l0"), Dsl("ge", [Dsl("ref", "@it"), 0])]),
                ],
                [
                    "List1 all ge 0",
                    True,
                    Dsl("all", [Dsl("ref", "l1"), Dsl("ge", [Dsl("ref", "@it"), 0])]),
                ],
                [
                    "List5 all ge 1",
                    False,
                    Dsl("all", [Dsl("ref", "l5"), Dsl("ge", [Dsl("ref", "@it"), 1])]),
                ],
                ##### filter
                [
                    "Array0 len filter lt 2",
                    0,
                    Dsl(
                        "len",
                        Dsl(
                            "filter",
                            [Dsl("ref", "a0"), Dsl("lt", [Dsl("ref", "@it"), 2])],
                        ),
                    ),
                ],
                [
                    "Array1 len filter lt 2",
                    1,
                    Dsl(
                        "len",
                        Dsl(
                            "filter",
                            [Dsl("ref", "a1"), Dsl("lt", [Dsl("ref", "@it"), 2])],
                        ),
                    ),
                ],
                [
                    "Array5 len filter lt 2",
                    2,
                    Dsl(
                        "len",
                        Dsl(
                            "filter",
                            [Dsl("ref", "a5"), Dsl("lt", [Dsl("ref", "@it"), 2])],
                        ),
                    ),
                ],
                [
                    "List0 len filter lt 2",
                    0,
                    Dsl(
                        "len",
                        Dsl(
                            "filter",
                            [Dsl("ref", "l0"), Dsl("lt", [Dsl("ref", "@it"), 2])],
                        ),
                    ),
                ],
                [
                    "List1 len filter lt 2",
                    1,
                    Dsl(
                        "len",
                        Dsl(
                            "filter",
                            [Dsl("ref", "l1"), Dsl("lt", [Dsl("ref", "@it"), 2])],
                        ),
                    ),
                ],
                [
                    "List5 len filter lt 2",
                    2,
                    Dsl(
                        "len",
                        Dsl(
                            "filter",
                            [Dsl("ref", "l5"), Dsl("lt", [Dsl("ref", "@it"), 2])],
                        ),
                    ),
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
        elif self.get_tracer()["language"] in ["nodejs", "ruby", "python", "php"]:
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
                [
                    "Hash0 any gt 1",
                    False,
                    Dsl("any", [Dsl("ref", "h0"), Dsl("gt", [get_hash_value, 1])]),
                ],
                [
                    "Hash1 any gt 1",
                    False,
                    Dsl("any", [Dsl("ref", "h1"), Dsl("gt", [get_hash_value, 1])]),
                ],
                [
                    "Hash5 any gt 1",
                    True,
                    Dsl("any", [Dsl("ref", "h5"), Dsl("gt", [get_hash_value, 1])]),
                ],
                ##### all
                [
                    "Hash0 all ge 0",
                    True,
                    Dsl("all", [Dsl("ref", "h0"), Dsl("ge", [get_hash_value, 0])]),
                ],
                [
                    "Hash1 all ge 0",
                    True,
                    Dsl("all", [Dsl("ref", "h1"), Dsl("ge", [get_hash_value, 0])]),
                ],
                [
                    "Hash5 all ge 1",
                    False,
                    Dsl("all", [Dsl("ref", "h5"), Dsl("ge", [get_hash_value, 1])]),
                ],
                ##### filter
                [
                    "Hash0 len filter lt 2",
                    0,
                    Dsl(
                        "len",
                        Dsl("filter", [Dsl("ref", "h0"), Dsl("lt", [get_hash_value, 2])]),
                    ),
                ],
                [
                    "Hash1 len filter lt 2",
                    1,
                    Dsl(
                        "len",
                        Dsl("filter", [Dsl("ref", "h1"), Dsl("lt", [get_hash_value, 2])]),
                    ),
                ],
                [
                    "Hash5 len filter lt 2",
                    2,
                    Dsl(
                        "len",
                        Dsl("filter", [Dsl("ref", "h5"), Dsl("lt", [get_hash_value, 2])]),
                    ),
                ],
            ],
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/collections")

    def test_expression_language_hash_operations(self):
        self._assert(expected_response=200)

    def setup_expression_language_hash_key_value(self):
        key_0: str | int = 0
        key_2: str | int = 2
        key_3: str | int = 3
        key_5: str | int = 5

        # In Node.js, object keys are always strings, so we need to compare with string literals
        # In other languages, the keys might be actual integers.
        if self.get_tracer()["language"] == "nodejs":
            key_3 = "3"
            key_5 = "5"
            key_0 = "0"
            key_2 = "2"

        language, method = self.get_tracer()["language"], "CollectionOperations"
        message_map, probes = self._create_expression_probes(
            method_name=method,
            expressions=[
                ## Testing @key and @value contextual variables for dictionary iteration
                ## Hash variables (h0, h1, h5) are dictionaries with integer keys and values
                ## where key i has value i (e.g., h5 = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4})
                ##### any with @key and @value
                [
                    "Hash5 any key eq 3",
                    True,
                    Dsl(
                        "any",
                        [Dsl("ref", "h5"), Dsl("eq", [Dsl("ref", "@key"), key_3])],
                    ),
                ],
                [
                    "Hash5 any value gt 3",
                    True,
                    Dsl("any", [Dsl("ref", "h5"), Dsl("gt", [Dsl("ref", "@value"), 3])]),
                ],
                [
                    "Hash1 any key eq 5",
                    False,
                    Dsl(
                        "any",
                        [Dsl("ref", "h1"), Dsl("eq", [Dsl("ref", "@key"), key_5])],
                    ),
                ],
                ##### all with @key and @value
                [
                    "Hash5 all key ge 0",
                    True,
                    Dsl(
                        "all",
                        [Dsl("ref", "h5"), Dsl("ge", [Dsl("ref", "@key"), key_0])],
                    ),
                ],
                [
                    "Hash5 all value ge 0",
                    True,
                    Dsl("all", [Dsl("ref", "h5"), Dsl("ge", [Dsl("ref", "@value"), 0])]),
                ],
                [
                    "Hash5 all key lt 3",
                    False,
                    Dsl(
                        "all",
                        [Dsl("ref", "h5"), Dsl("lt", [Dsl("ref", "@key"), key_3])],
                    ),
                ],
                ##### filter with @key and @value
                [
                    "Hash5 len filter value lt 2",
                    2,
                    Dsl(
                        "len",
                        Dsl(
                            "filter",
                            [Dsl("ref", "h5"), Dsl("lt", [Dsl("ref", "@value"), 2])],
                        ),
                    ),
                ],
                [
                    "Hash5 len filter key gt 2",
                    2,
                    Dsl(
                        "len",
                        Dsl(
                            "filter",
                            [Dsl("ref", "h5"), Dsl("gt", [Dsl("ref", "@key"), key_2])],
                        ),
                    ),
                ],
            ],
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/collections")

    def test_expression_language_hash_key_value(self):
        self._assert(expected_response=200)

    ############ nulls ############
    def setup_expression_language_nulls_true(self):
        language, method = self.get_tracer()["language"], "Nulls"
        expressions = [["pii eq null", True, Dsl("eq", [Dsl("ref", "pii"), None])]]

        # In Node.js, numbers and strings cannot be null as they are not objects
        if language != "nodejs":
            expressions.extend(
                [
                    [
                        "intValue eq null",
                        True,
                        Dsl("eq", [Dsl("ref", "intValue"), None]),
                    ],
                    [
                        "strValue eq null",
                        True,
                        Dsl("eq", [Dsl("ref", "strValue"), None]),
                    ],
                ]
            )

        message_map, probes = self._create_expression_probes(
            method_name=method,
            expressions=expressions,
            lines=self.method_and_language_to_line_number(method, language),
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/null")

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

    def test_expression_language_nulls_false(self):
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
