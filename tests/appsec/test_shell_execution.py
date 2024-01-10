# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
from utils import coverage, interfaces, weblog, features


@features.appsec_shell_execution_tracing
@coverage.basic
class Test_ShellExecution:
    """Test shell execution tracing"""

    def setup_track_cmd_exec(self):
        self.r_cmd_exec = weblog.post(
            "/shell_execution",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {"command": "echo", "options": {"shell": False}, "args": "foo"}
            ),
        )

    def test_track_cmd_exec(self):
        for _, trace in interfaces.library.get_traces(request=self.r_cmd_exec):
            for span in trace:
                if span["name"] == "command_execution":
                    shell_exec_span = span

        assert self.r_cmd_exec.status_code == 200
        assert (
            shell_exec_span is not None
        ), f"shell_exec_span hasn't be found for {self.r_cmd_exec.request.url}"
        assert shell_exec_span["name"] == "command_execution"
        assert shell_exec_span["meta"]["component"] == "subprocess"
        assert shell_exec_span["meta"]["cmd.exec"] == '["echo","foo"]'
        assert shell_exec_span["meta"]["cmd.exit_code"] == "0"

    def setup_track_shell_exec(self):
        self.r_cmd_exec = weblog.post(
            "/shell_execution",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {"command": "echo", "options": {"shell": True}, "args": "foo"}
            ),
        )

    def test_track_shell_exec(self):
        for _, trace in interfaces.library.get_traces(request=self.r_cmd_exec):
            for span in trace:
                if span["name"] == "command_execution":
                    shell_exec_span = span

        assert self.r_cmd_exec.status_code == 200
        assert (
            shell_exec_span is not None
        ), f"shell_exec_span hasn't be found for {self.r_cmd_exec.request.url}"
        assert shell_exec_span["name"] == "command_execution"
        assert shell_exec_span["meta"]["component"] == "subprocess"
        assert shell_exec_span["meta"]["cmd.shell"] == '["echo","foo"]'
        assert shell_exec_span["meta"]["cmd.exit_code"] == "0"

    def setup_truncation(self):
        args = "foo".ljust(32000, "o")
        self.r_cmd_exec = weblog.post(
            "/shell_execution",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {"command": "echo", "options": {"shell": False}, "args": args}
            ),
        )

    def test_truncation(self):
        for _, trace in interfaces.library.get_traces(request=self.r_cmd_exec):
            for span in trace:
                if span["name"] == "command_execution":
                    shell_exec_span = span

        assert self.r_cmd_exec.status_code == 200
        assert (
            shell_exec_span is not None
        ), f"shell_exec_span hasn't be found for {self.r_cmd_exec.request.url}"
        assert shell_exec_span["name"] == "command_execution"
        assert shell_exec_span["meta"]["component"] == "subprocess"
        assert shell_exec_span["meta"]["cmd.exec"] == '["echo","fo"]'
        assert shell_exec_span["meta"]["cmd.exit_code"] == "0"

    def setup_obfuscation(self):
        args = "password 1234"
        self.r_cmd_exec = weblog.post(
            "/shell_execution",
            headers={"Content-Type": "application/json"},
            data=json.dumps(
                {"command": "echo", "options": {"shell": False}, "args": args}
            ),
        )

    def test_obfuscation(self):
        for _, trace in interfaces.library.get_traces(request=self.r_cmd_exec):
            for span in trace:
                if span["name"] == "command_execution":
                    shell_exec_span = span

        assert self.r_cmd_exec.status_code == 200
        assert (
            shell_exec_span is not None
        ), f"shell_exec_span hasn't be found for {self.r_cmd_exec.request.url}"
        assert shell_exec_span["name"] == "command_execution"
        assert shell_exec_span["meta"]["component"] == "subprocess"
        assert shell_exec_span["meta"]["cmd.exec"] == '["echo","password","?"]'
        assert shell_exec_span["meta"]["cmd.exit_code"] == "0"
