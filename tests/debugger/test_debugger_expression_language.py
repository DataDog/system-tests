# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as base
import re
from utils import (
    scenarios,
    interfaces,
    weblog,
    features,
    remote_config as rc,
)


@features.debugger_expression_language
@scenarios.debugger_expression_language
class Test_Debugger_Expression_Language(base._Base_Debugger_Test):
    version = 0

    def _setup(self, probes_name: str, request_path: str):
        Test_Debugger_Expression_Language.version += 1

        probes = base.read_probes(probes_name)
        self.expected_probe_ids = base.extract_probe_ids(probes)
        self.rc_state = rc.send_debugger_command(probes=probes, version=Test_Debugger_Expression_Language.version)

        interfaces.agent.wait_for(self.wait_for_all_probes_installed, timeout=30)
        self.weblog_responses = [weblog.get(request_path)]

    def setup_expression_language_access_variables(self):
        self._setup("expression_language_access_variables", "/debugger/expression?inputValue=asd")

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
        self._setup("expression_language_access_exception", "/debugger/expression/exception")

    def test_expression_language_access_exception(self):
        self.assert_all_states_not_error()
        self.assert_all_probes_are_installed()

        expected_messages = {
            "log170aa-expr-lang-0011-1478a6method": r"Accessing exception variable. .*Hello from exception",
        }

        self._validate_expression_language_messages(expected_messages)

    def setup_expression_language_comparison_operators(self):
        self._setup(
            "expression_language_comparison_operators", "/debugger/expression/comparison-operators?inputValue=5"
        )

    def test_expression_language_comparison_operators(self):
        self.assert_all_states_not_error()
        self.assert_all_probes_are_installed()
        self.assert_all_weblog_responses_ok()

        expected_messages = {
            "log170aa-expr-lang-0001-1479a6method": r"Testing 5 eq 5. Result is: [Tt]rue",
            "log170aa-expr-lang-0002-1479a6method": r"Testing 5 lt 10. Result is: [Tt]rue",
            "log170aa-expr-lang-0003-1479a6method": r"Testing 5 gt 0. Result is: [Tt]rue",
            "log170aa-expr-lang-0004-1479a6method": r"Testing 5 ne 0. Result is: [Tt]rue",
            "log170aa-expr-lang-0005-1479a6method": r"Testing 5 le 10. Result is: [Tt]rue",
            "log170aa-expr-lang-0006-1479a6method": r"Testing 5 le 5. Result is: [Tt]rue",
            "log170aa-expr-lang-0007-1479a6method": r"Testing 5 ge 0. Result is: [Tt]rue",
            "log170aa-expr-lang-0008-1479a6method": r"Testing 5 ge 5. Result is: [Tt]rue",
            "log170aa-expr-lang-0011-1479a6method": r"Testing 5 eq 0. Result is: [Ff]alse",
            "log170aa-expr-lang-0012-1479a6method": r"Testing 5 lt 0. Result is: [Ff]alse",
            "log170aa-expr-lang-0013-1479a6method": r"Testing 5 gt 10. Result is: [Ff]alse",
            "log170aa-expr-lang-0014-1479a6method": r"Testing 5 ne 5. Result is: [Ff]alse",
            "log170aa-expr-lang-0015-1479a6method": r"Testing 5 le 0. Result is: [Ff]alse",
            "log170aa-expr-lang-0016-1479a6method": r"Testing 5 le 0. Result is: [Ff]alse",
            "log170aa-expr-lang-0017-1479a6method": r"Testing 5 ge 10. Result is: [Ff]alse",
            "log170aa-expr-lang-0018-1479a6method": r"Testing 5 ge 10. Result is: [Ff]alse",
        }

        self._validate_expression_language_messages(expected_messages)

    def _validate_expression_language_messages(self, expected_message_map):
        agent_logs_endpoint_requests = list(interfaces.agent.get_data(path_filters="/api/v2/logs"))

        not_found_ids = set(self.expected_probe_ids)
        for request in agent_logs_endpoint_requests:
            content = request["request"]["content"]

            if content is not None:
                for content in content:
                    probe_id = content["debugger"]["snapshot"]["probe"]["id"]

                    if probe_id in expected_message_map:
                        not_found_ids.remove(probe_id)
                        assert re.search(
                            expected_message_map[probe_id], content["message"]
                        ), f"Message for probe id {probe_id} not found"

        assert not not_found_ids, f"The following probes were not found: {', '.join(not_found_ids)}"
