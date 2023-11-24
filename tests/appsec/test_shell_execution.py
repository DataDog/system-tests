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
        context.library == "php"
        and context.weblog_variant.contains("-7.")
        and not context.weblog_variant.contains("7.4"),
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

    # This test is wrong. cmd.shell should not be in array notation. Citing the RFC:
    # > As an example, subprocess.run(["ls", "-l"], shell=True) will produce
    # > "cmd.shell": "ls -a" [sic]
    @irrelevant(library="php", reason="The test is wrong")
    def test_track_shell_exec(self):
        shell_exec_span = self.fetch_command_execution_span(self.r_shell_exec)

        assert shell_exec_span["meta"]["cmd.shell"] == '["echo","foo"]'
        assert shell_exec_span["meta"]["cmd.exit_code"] == "0"

    def setup_track_shell_exec_correct(self):
        self.r_shell_exec_correct = weblog.post(
            "/shell_execution",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"command": "echo", "options": {"shell": True}, "args": "foo"}),
        )

    @bug(
        context.library != "php" and context.library != "java",
        reason="Possible reliance on wrong test. See " "test_track_shell_exec",
    )
    @irrelevant(library="java", reason="No method for shell execution in Java")
    def test_track_shell_exec_correct(self):
        shell_exec_span = self.fetch_command_execution_span(self.r_shell_exec_correct)

        assert shell_exec_span["meta"]["cmd.shell"] == "echo foo"
        assert shell_exec_span["meta"]["cmd.exit_code"] == "0"

    def setup_truncation(self):
        args = "foo".ljust(32000, "o")
        self.r_truncation = weblog.post(
            "/shell_execution",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"command": "echo", "options": {"shell": False}, "args": args}),
        )

    # The RFC never says the argument should be truncated to 2 characters. It says
    # the argument should be truncated **by** 2 characters (the length of "ls"
    # in the example in the RFC).
    @irrelevant(library="php", reason="The test is wrong")
    def test_truncation(self):
        shell_exec_span = self.fetch_command_execution_span(self.r_truncation)

        assert shell_exec_span["meta"]["cmd.exec"] == '["echo","fo"]'
        assert shell_exec_span["meta"]["cmd.exit_code"] == "0"

    def setup_truncated_correct(self):
        args = ["a" * 4096, "arg"]
        self.r_truncation_correct = weblog.post(
            "/shell_execution",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"command": "echo", "options": {"shell": False}, "args": args}),
        )

    @bug(context.library != "php", reason="Possible reliance on wrong test. See comment in test_truncation")
    @irrelevant(
        context.library == "php"
        and context.weblog_variant.contains("-7.")
        and not context.weblog_variant.contains("7.4"),
        reason="For PHP 7.4+",
    )
    def test_truncated_correct(self):
        shell_exec_span = self.fetch_command_execution_span(self.r_truncation_correct)

        assert shell_exec_span["meta"]["cmd.exec"] == '["echo","' + "a" * 4092 + '",""]'
        assert shell_exec_span["meta"]["cmd.exit_code"] == "0"

    def setup_obfuscation(self):
        args = "password 1234"
        self.r_obfuscation = weblog.post(
            "/shell_execution",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"command": "echo", "options": {"shell": False}, "args": args}),
        )

    def test_obfuscation(self):
        shell_exec_span = self.fetch_command_execution_span(self.r_obfuscation)

        assert shell_exec_span["meta"]["cmd.exec"] == '["echo","password","?"]'
        assert shell_exec_span["meta"]["cmd.exit_code"] == "0"
