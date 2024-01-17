# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
from utils import coverage, interfaces, weblog, features, irrelevant
from utils._context.core import context


@features.appsec_shell_execution_tracing
@coverage.basic
class Test_ShellExecution:
    """Test shell execution tracing"""

    @staticmethod
    def fetch_command_execution_span(r):
        for _, trace in interfaces.library.get_traces(request=r):
            for span in trace:
                if span["name"] == "command_execution":
                    command_exec_span = span

        assert r.status_code == 200
        assert command_exec_span is not None, f"command execution span hasn't be found for {r.url}"
        assert command_exec_span["name"] == "command_execution"
        assert command_exec_span["meta"]["component"] == "subprocess"
        return command_exec_span

    def setup_track_cmd_exec(self):
        self.r_cmd_exec = weblog.post(
            "/shell_execution",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"command": "echo", "options": {"shell": False}, "args": "foo"}),
        )

    @irrelevant(
        context.library == "php" and "-7." in context.weblog_variant and "7.4" not in context.weblog_variant,
        reason="For PHP 7.4+",
    )
    def test_track_cmd_exec(self):
        shell_exec_span = self.fetch_command_execution_span(self.r_cmd_exec)
        assert shell_exec_span["meta"]["cmd.exec"] == '["echo","foo"]'
        assert shell_exec_span["meta"]["cmd.exit_code"] == "0"

    def setup_track_shell_exec(self):
        self.r_shell_exec = weblog.post(
            "/shell_execution",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"command": "echo", "options": {"shell": True}, "args": "foo"}),
        )

    @irrelevant(library="java", reason="No method for shell execution in Java")
    def test_track_shell_exec(self):
        shell_exec_span = self.fetch_command_execution_span(self.r_shell_exec)

        assert shell_exec_span["meta"]["cmd.shell"] == "echo foo"
        assert shell_exec_span["meta"]["cmd.exit_code"] == "0"

    def setup_truncated(self):
        args = ["a" * 4096, "arg"]
        self.r_truncation = weblog.post(
            "/shell_execution",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"command": "echo", "options": {"shell": False}, "args": args}),
        )

    @irrelevant(
        context.library == "php" and "-7." in context.weblog_variant and "7.4" not in context.weblog_variant,
        reason="For PHP 7.4+",
    )
    def test_truncated(self):
        shell_exec_span = self.fetch_command_execution_span(self.r_truncation)
        assert shell_exec_span["meta"]["cmd.exec"] == '["echo","' + "a" * 4092 + '",""]'
        assert shell_exec_span["meta"]["cmd.truncated"] == "true"
        assert shell_exec_span["meta"]["cmd.exit_code"] == "0"

    def setup_obfuscation(self):
        args = "password 1234"
        self.r_obfuscation = weblog.post(
            "/shell_execution",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"command": "echo", "options": {"shell": False}, "args": args}),
        )

    @irrelevant(
        context.library == "php" and "-7." in context.weblog_variant and "7.4" not in context.weblog_variant,
        reason="For PHP 7.4+",
    )
    def test_obfuscation(self):
        shell_exec_span = self.fetch_command_execution_span(self.r_obfuscation)

        assert shell_exec_span["meta"]["cmd.exec"] == '["echo","password","?"]'
        assert shell_exec_span["meta"]["cmd.exit_code"] == "0"
