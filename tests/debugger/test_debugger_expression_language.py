# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as base
import re, json
from utils import scenarios, interfaces, weblog, features, remote_config as rc, bug


@features.debugger_expression_language
@scenarios.debugger_expression_language
class Test_Debugger_Expression_Language(base._Base_Debugger_Test):
    version = 0
    message_map = {}
    tracer = None

    def _setup(self, probes, request_path):
        self.expected_probe_ids = base.extract_probe_ids(probes)

        Test_Debugger_Expression_Language.version += 1
        self.rc_state = rc.send_debugger_command(probes=probes, version=Test_Debugger_Expression_Language.version)

        interfaces.agent.wait_for(self.wait_for_all_probes_installed, timeout=30)
        self.weblog_responses = [weblog.get(request_path)]

    def setup_expression_language_access_variables(self):
        self._setup(base.read_probes("expression_language_access_variables"), "/debugger/expression?inputValue=asd")

    def test_expression_language_access_variables(self):
        self.assert_all_states_not_error()
        self.assert_all_probes_are_installed()
        self.assert_all_weblog_responses_ok()

        expected_messages = {
            "log170aa-expr-lang-0001-1478a6method": "Accessing input variable. Value is: asd",
            "log170aa-expr-lang-0002-1478a6method": r"Accessing return variable. Value is:.*Great success number 3",
            "log170aa-expr-lang-0003-1478a6method": "Accessing local variable. Value is: 3",
            "log170aa-expr-lang-0004-1478a6method": "Accessing complex object int variable. Value is: 1",
            "log170aa-expr-lang-0005-1478a6method": "Accessing complex object double variable. Value is: 1.1",
            "log170aa-expr-lang-0006-1478a6method": "Accessing complex object string variable. Value is: one",
            "log170aa-expr-lang-0007-1478a6method": r"Accessing complex object bool variable. Value is: [Tt]rue",
            "log170aa-expr-lang-0008-1478a6method": "Accessing complex object collection first variable. Value is: one",
            "log170aa-expr-lang-0009-1478a6method": "Accessing complex object dictionary 'two' keyword. Value is: 2",
            "log170aa-expr-lang-0010-1478a6method": r"Accessing duration variable. Value is: \d+(\.\d+)?",
        }

        self._validate_expression_language_messages(expected_messages)

    def setup_expression_language_access_exception(self):
        self._setup(base.read_probes("expression_language_access_exception"), "/debugger/expression/exception")

    def test_expression_language_access_exception(self):
        self.assert_all_states_not_error()
        self.assert_all_probes_are_installed()

        expected_messages = {
            "log170aa-expr-lang-0011-1478a6method": r"Accessing exception variable. .*Hello from exception",
        }

        self._validate_expression_language_messages(expected_messages)

    def setup_expression_language_comparison_operators(self):
        message_map, probes = self._create_expression_probes(
            methodName="ExpressionOperators",
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
                ["floatValue ne 0", True, Dsl("ne", [Dsl("ref", "floatValue"), 3.14])],
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
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/operators?intValue=5&floatValue=3.14&strValue=haha")

    @bug(library="dotnet", reason="DEBUG-2524")
    def test_expression_language_comparison_operators(self):
        self.assert_all_states_not_error()
        self.assert_all_probes_are_installed()
        self.assert_all_weblog_responses_ok()

        self._validate_expression_language_messages(self.message_map)

    def setup_expression_language_instance_of(self):
        message_map, probes = self._create_expression_probes(
            methodName="ExpressionOperators",
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
                    "this instanceof controller",
                    True,
                    Dsl("instanceof", [Dsl("ref", "this"), self._get_type("controller")]),
                ],
                [
                    "intValue instanceof float",
                    False,
                    Dsl("instanceof", [Dsl("ref", "intValue"), self._get_type("int")]),
                ],
                [
                    "floatValue instanceof int",
                    False,
                    Dsl("instanceof", [Dsl("ref", "floatValue"), self._get_type("int")]),
                ],
                [
                    "strValue instanceof float",
                    False,
                    Dsl("instanceof", [Dsl("ref", "strValue"), self._get_type("float")]),
                ],
                ["this instanceof string", False, Dsl("instanceof", [Dsl("ref", "this"), self._get_type("string")])],
            ],
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/operators?intValue=5&floatValue=3.14&strValue=haha")

    @bug(library="java", reason="DEBUG-2527")
    @bug(library="dotnet", reason="DEBUG-2530")
    def test_expression_language_instance_of(self):
        self.assert_all_states_not_error()
        self.assert_all_probes_are_installed()
        self.assert_all_weblog_responses_ok()

        self._validate_expression_language_messages(self.message_map)

    def setup_expression_language_logical_operators(self):

        message_map, probes = self._create_expression_probes(
            methodName="ExpressionOperators",
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
                ["not intValue ne 10", True, Dsl("not", Dsl("ne", [Dsl("ref", "intValue"), 5])),],
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
                ["not intValue eq 10", False, Dsl("not", Dsl("eq", [Dsl("ref", "intValue"), 5])),],
            ],
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/operators?intValue=5&floatValue=3.14&strValue=haha")

    def test_expression_language_logical_operators(self):
        self.assert_all_states_not_error()
        self.assert_all_probes_are_installed()
        self.assert_all_weblog_responses_ok()

        self._validate_expression_language_messages(self.message_map)

    @bug(library="dotnet", reason="DEBUG-2560")
    def setup_expression_language_string_operations(self):

        message_map, probes = self._create_expression_probes(
            methodName="StringOperations",
            expressions=[
                ##### isempty
                ["strValue isEmpty", False, Dsl("isEmpty", Dsl("ref", "strValue"))],
                ["emptyString isEmpty", True, Dsl("isEmpty", Dsl("ref", "emptyString"))],
                ["nullString isEmpty", True, Dsl("isEmpty", Dsl("ref", "nullString"))],
                ##### len
                ["strValue len", 14, Dsl("len", Dsl("ref", "strValue"))],
                ["emptyString len", 0, Dsl("len", Dsl("ref", "emptyString"))],
                ##### substring
                ["strValue substring 0 5", "veryl", Dsl("substring", [Dsl("ref", "strValue"), 0, 5])],
                ["strValue substring 5 10", "ongst", Dsl("substring", [Dsl("ref", "strValue"), 5, 10])],
                ["strValue substring 0 0", "", Dsl("substring", [Dsl("ref", "strValue"), 0, 0])],
                ["emptyStr substring 0 0", "", Dsl("substring", [Dsl("ref", "emptyStr"), 0, 0])],
                ##### startsWith
                ["strValue startsWith very", True, Dsl("startsWith", [Dsl("ref", "strValue"), "very"])],
                ["strValue startsWith foo", False, Dsl("startsWith", [Dsl("ref", "strValue"), "foo"])],
                ["emptyString startsWith empty", True, Dsl("startsWith", [Dsl("ref", "emptyString"), ""])],
                ["emptyString startsWith some", False, Dsl("startsWith", [Dsl("ref", "emptyString"), "some"]),],
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
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/strings?strValue=verylongstring")

    def test_expression_language_string_operations(self):
        self.assert_all_states_not_error()
        self.assert_all_probes_are_installed()
        self.assert_all_weblog_responses_ok()

        self._validate_expression_language_messages(self.message_map)

    def _get_type(self, value_type):
        if self.tracer is None:
            tracer = base.get_tracer()

        intance_type = ""

        if tracer["language"] == "dotnet":
            if value_type == "int":
                intance_type = "System.Int32"
            elif value_type == "float":
                intance_type = "System.Single"
            elif value_type == "string":
                intance_type = "System.String"
            elif value_type == "controller":
                intance_type = "weblog.DebuggerController"
            else:
                intance_type = value_type
        elif tracer["language"] == "java":
            if value_type == "int":
                intance_type = "java.lang.int"
            elif value_type == "float":
                intance_type = "java.lang.float"
            elif value_type == "string":
                intance_type = "java.lang.String"
            elif value_type == "controller":
                intance_type = "com.datadoghq.system_tests.springboot.DebuggerController"
            else:
                intance_type = value_type
        else:
            intance_type = value_type
        return intance_type

    def _create_expression_probes(self, methodName, expressions):
        probes = []
        expected_message_map = {}

        for expression in expressions:
            expression_to_test, expected_result, dsl = expression
            message = f"Expression to test: '{expression_to_test}'. Result is: "

            if isinstance(expected_result, bool):
                expected_result = "[Tt]rue" if expected_result else "[Ff]alse"
            else:
                expected_result = str(expected_result)

            probe = base.read_probes("expression_probe_base")[0]
            probe["id"] = base.generate_probe_id("log")
            probe["where"]["methodName"] = methodName
            probe["segments"] = Segment().add_str(message).add_dsl(dsl).to_dict()
            probes.append(probe)

            expected_message_map[probe["id"]] = message + expected_result

        return expected_message_map, probes

    def _validate_expression_language_messages(self, expected_message_map):
        agent_logs_endpoint_requests = list(interfaces.agent.get_data(path_filters="/api/v2/logs"))

        not_found_ids = set(self.expected_probe_ids)
        error_messages = []

        for request in agent_logs_endpoint_requests:
            content = request["request"]["content"]

            if content is not None:
                for content in content:
                    probe_id = content["debugger"]["snapshot"]["probe"]["id"]

                    if probe_id in expected_message_map:
                        not_found_ids.remove(probe_id)

                        if not re.search(expected_message_map[probe_id], content["message"]):
                            error_messages.append(
                                f"Message for probe id {probe_id} is wrong. \n Expected: {expected_message_map[probe_id]}. \n Found: {content['message']}."
                            )

                            evaluation_errors = content["debugger"]["snapshot"].get("evaluationErrors", [])
                            for error in evaluation_errors:
                                error_messages.append(
                                    f" Evaluation error in probe id {probe_id}: {error['expr']} - {error['message']}\n"
                                )

        assert not error_messages, "Errors occurred during validation:\n" + "\n".join(error_messages)
        assert not not_found_ids, f"The following probes were not found: {', '.join(not_found_ids)}"


class Segment:
    def __init__(self):
        self.segments = []

    def add_str(self, string):
        self.segments.append({"str": string})
        return self

    def add_dsl(self, dsl_creator):
        self.segments.append({"dsl": "", "json": dsl_creator.to_dict()})
        return self

    def to_dict(self):
        return self.segments

    def to_json(self):
        return json.dumps(self.to_dict())


class Dsl:
    def __init__(self, operator, value):
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
