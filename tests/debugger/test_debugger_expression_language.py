# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as base
import re
from utils import scenarios, interfaces, weblog, features


@features.debugger_expression_language
@scenarios.debugger_expression_language
class Test_Debugger_Expression_Language(base._Base_Debugger_Test):
    def _validate_expression_language_messages(self, expected_message_map):
        agent_logs_endpoint_requests = list(interfaces.agent.get_data(path_filters="/api/v2/logs"))

        for request in agent_logs_endpoint_requests:
            content = request["request"]["content"]

            if content is not None:
                for content in content:
                    probe_id = content["debugger"]["snapshot"]["probe"]["id"]

                    if probe_id in expected_message_map:
                        message = content["message"]
                        assert re.search(expected_message_map[probe_id], message), "Message not found"

    def setup_expression_language_accessing_variables(self):
        self.expected_probe_ids = [
            "log170aa-expr-lang-0001-1478a6method",
            "log170aa-expr-lang-0002-1478a6method",
            "log170aa-expr-lang-0003-1478a6method",
            "log170aa-expr-lang-0004-1478a6method",
            "log170aa-expr-lang-0005-1478a6method",
            "log170aa-expr-lang-0006-1478a6method",
            "log170aa-expr-lang-0007-1478a6method",
            "log170aa-expr-lang-0008-1478a6method",
            "log170aa-expr-lang-0009-1478a6method",
            "log170aa-expr-lang-0010-1478a6method",
        ]

        interfaces.library.wait_for_remote_config_request()
        interfaces.agent.wait_for(self.wait_for_all_probes_installed, timeout=30)
        self.weblog_responses = [weblog.get("/debugger/expression?inputValue=asd")]

    def test_expression_language_accessing_variables(self):
        self.assert_remote_config_is_sent()
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

    def setup_expression_language_accessing_exception(self):
        self.expected_probe_ids = [
            "log170aa-expr-lang-0011-1478a6method",
        ]

        interfaces.library.wait_for_remote_config_request()
        interfaces.agent.wait_for(self.wait_for_all_probes_installed, timeout=30)
        self.weblog_responses = [weblog.get("/debugger/expression/exception")]

    def test_expression_language_accessing_exception(self):
        self.assert_remote_config_is_sent()
        self.assert_all_probes_are_installed()

        expected_messages = {
            "log170aa-expr-lang-0011-1478a6method": r"Accessing exception variable. .*Hello from exception",
        }

        self._validate_expression_language_messages(expected_messages)
