# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as base
import re
from utils import scenarios, interfaces, weblog, features, remote_config as rc, bug


@features.debugger_expression_language
@scenarios.debugger_expression_language
class Test_Debugger_Expression_Language(base._Base_Debugger_Test):
    version = 0
    message_map = {}

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
        def _create_comparison_probes(replacements):
            probes = []
            message_map = {}

            for replacement in replacements:
                ref_value_name, ref_value, operator, value, expected_result = replacement

                probe = base.read_probes("expression_language_comparison_operators")[0]
                probe["id"] = base.generate_probe_id("log")

                str_segment = probe["segments"][0]
                str_segment["str"] = str_segment["str"].replace("[REF_VALUE_NAME]", str(ref_value_name))
                str_segment["str"] = str_segment["str"].replace("[REF_VALUE]", str(ref_value))
                str_segment["str"] = str_segment["str"].replace("[VALUE]", str(value))
                str_segment["str"] = str_segment["str"].replace("[OPERATOR]", str(operator))

                message_map[probe["id"]] = str_segment["str"] + "[Tt]rue" if expected_result else "[Ff]alse"

                comparison_segment = probe["segments"][1]
                comparison_segment["json"]["[OPERATOR]"][0]["ref"] = ref_value_name
                comparison_segment["json"]["[OPERATOR]"][1] = value
                comparison_segment["json"][str(operator)] = comparison_segment["json"].pop("[OPERATOR]")

                probes.append(probe)

            return message_map, probes

        message_map, probes = _create_comparison_probes(
            [
                ["intValue", 5, "eq", 5, True],
                ["intValue", 5, "ne", 0, True],
                ["intValue", 5, "lt", 10, True],
                ["intValue", 5, "gt", 0, True],
                ["intValue", 5, "le", 10, True],
                ["intValue", 5, "le", 5, True],
                ["intValue", 5, "ge", 0, True],
                ["intValue", 5, "ge", 5, True],
                ["intValue", 5, "eq", 0, False],
                ["intValue", 5, "lt", 0, False],
                ["intValue", 5, "gt", 10, False],
                ["intValue", 5, "ne", 5, False],
                ["intValue", 5, "le", 0, False],
                ["intValue", 5, "ge", 10, False],
                ["floatValue", 3.14, "ne", 0, True],
                ["floatValue", 3.14, "ne", 0.1, True],
                ["floatValue", 3.14, "lt", 10, True],
                ["floatValue", 3.14, "lt", 10.10, True],
                ["floatValue", 3.14, "gt", 0, True],
                ["floatValue", 3.14, "gt", 0.0, True],
                ["floatValue", 3.14, "le", 5, True],
                ["floatValue", 3.14, "le", 5.5, True],
                ["floatValue", 3.14, "ge", 0, True],
                ["floatValue", 3.14, "ge", 0.0, True],
                ["floatValue", 3.14, "eq", 0, False],
                ["floatValue", 3.14, "eq", 0.0, False],
                ["floatValue", 3.14, "lt", 0, False],
                ["floatValue", 3.14, "lt", 0.0, False],
                ["floatValue", 3.14, "gt", 10, False],
                ["floatValue", 3.14, "gt", 10.10, False],
                ["floatValue", 3.14, "le", 0, False],
                ["floatValue", 3.14, "le", 0.0, False],
                ["floatValue", 3.14, "ge", 10, False],
                ["floatValue", 3.14, "ge", 10.10, False],
                ["strValue", "haha", "eq", "haha", True],
                ["strValue", "haha", "ne", "hoho", True],
                ["strValue", "haha", "lt", "z", True],
                ["strValue", "haha", "gt", "a", True],
                ["strValue", "haha", "le", "haha", True],
                ["strValue", "haha", "le", "z", True],
                ["strValue", "haha", "ge", "a", True],
                ["strValue", "haha", "ge", "haha", True],
                ["strValue", "haha", "eq", "hoho", False],
                ["strValue", "haha", "lt", "a", False],
                ["strValue", "haha", "gt", "z", False],
                ["strValue", "haha", "le", "a", False],
                ["strValue", "haha", "ge", "z", False],
            ]
        )

        self.message_map = message_map
        self._setup(probes, "/debugger/expression/comparison-operators?intValue=5&floatValue=3.14&strValue=haha")

    @bug(library="dotnet", reason="Comparison operators on float and string values are buggy")
    def test_expression_language_comparison_operators(self):
        self.assert_all_states_not_error()
        self.assert_all_probes_are_installed()
        self.assert_all_weblog_responses_ok()

        self._validate_expression_language_messages(self.message_map)

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
                                f"Message for probe id {probe_id} is worng. \n Expected: {expected_message_map[probe_id]}. \n Found: {content['message']}"
                            )

                            evaluation_errors = content["debugger"]["snapshot"].get("evaluationErrors", [])
                            for error in evaluation_errors:
                                error_messages.append(
                                    f" Evaluation error in probe id {probe_id}: {error['expr']} - {error['message']}\n"
                                )

        assert not error_messages, "Errors occurred during validation:\n" + "\n".join(error_messages)
        assert not not_found_ids, f"The following probes were not found: {', '.join(not_found_ids)}"
