# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import bug, context, interfaces, weblog, features, irrelevant, rfc
from utils._weblog import HttpResponse


@rfc("https://docs.google.com/document/d/1YYxOB1nM032H-lgXrVml9mukMhF4eHVIzyK9H_PvrSY/edit#heading=h.o5gstqo08gu5")
@features.appsec_shell_execution_tracing
@bug(context.library < "java@1.29.0", reason="APPSEC-10243")
class Test_ShellExecution:
    """Test shell execution tracing"""

    @staticmethod
    def fetch_command_execution_span(r: HttpResponse) -> dict:
        assert r.status_code == 200

        traces = [t for _, t in interfaces.library.get_traces(request=r)]
        assert traces, "No traces found"
        assert len(traces) == 1
        spans = traces[0]
        spans = [s for s in spans if s["name"] == "command_execution"]
        assert spans, "No command_execution span found"
        assert len(spans) == 1, "More than one command_execution span found"

        span = spans[0]
        assert span["name"] == "command_execution"
        assert span["type"] == "system"
        assert span["meta"]["component"] == "subprocess"
        return span

    def setup_track_cmd_exec(self):
        self.r_cmd_exec = weblog.post(
            "/shell_execution", json={"command": "echo", "options": {"shell": False}, "args": "foo"}
        )

    @irrelevant(
        context.library == "php" and "-7." in context.weblog_variant and "7.4" not in context.weblog_variant,
        reason="For PHP 7.4+",
    )
    def test_track_cmd_exec(self):
        span = self.fetch_command_execution_span(self.r_cmd_exec)
        assert span["resource"] == "echo"
        assert span["meta"]["cmd.exec"] == '["echo","foo"]'
        assert span["meta"]["cmd.exit_code"] == "0"

    def setup_track_shell_exec(self):
        self.r_shell_exec = weblog.post(
            "/shell_execution", json={"command": "echo", "options": {"shell": True}, "args": "foo"}
        )

    @irrelevant(library="java", reason="No method for shell execution in Java")
    def test_track_shell_exec(self):
        span = self.fetch_command_execution_span(self.r_shell_exec)
        assert span["resource"] == "sh"
        assert span["meta"]["cmd.shell"] == "echo foo"
        assert span["meta"]["cmd.exit_code"] == "0"

    def setup_truncate_1st_argument(self):
        args = ["a" * 4096, "arg"]
        self.r_truncation = weblog.post(
            "/shell_execution", json={"command": "echo", "options": {"shell": False}, "args": args}
        )

    @irrelevant(
        context.library == "php" and "-7." in context.weblog_variant and "7.4" not in context.weblog_variant,
        reason="For PHP 7.4+",
    )
    @bug(library="java", reason="APPSEC-55672")
    @bug(library="php", reason="APPSEC-55673")
    def test_truncate_1st_argument(self):
        span = self.fetch_command_execution_span(self.r_truncation)
        assert span["resource"] == "echo"
        assert span["meta"]["cmd.exec"] == '["echo","aa",""]'
        assert span["meta"]["cmd.truncated"] == "true"
        assert span["meta"]["cmd.exit_code"] == "0"

    def setup_truncate_blank_2nd_argument(self):
        args = ["a" * 4092, "arg"]
        self.r_truncation = weblog.post(
            "/shell_execution", json={"command": "echo", "options": {"shell": False}, "args": args}
        )

    @irrelevant(
        context.library == "php" and "-7." in context.weblog_variant and "7.4" not in context.weblog_variant,
        reason="For PHP 7.4+",
    )
    @bug(library="java", reason="APPSEC-55672")
    def test_truncate_blank_2nd_argument(self):
        span = self.fetch_command_execution_span(self.r_truncation)
        assert span["resource"] == "echo"
        assert span["meta"]["cmd.exec"] == '["echo","' + "a" * 4092 + '",""]'
        assert span["meta"]["cmd.truncated"] == "true"
        assert span["meta"]["cmd.exit_code"] == "0"

    def setup_obfuscation(self):
        args = "password 1234"
        self.r_obfuscation = weblog.post(
            "/shell_execution", json={"command": "echo", "options": {"shell": False}, "args": args}
        )

    @irrelevant(
        context.library == "php" and "-7." in context.weblog_variant and "7.4" not in context.weblog_variant,
        reason="For PHP 7.4+",
    )
    def test_obfuscation(self):
        span = self.fetch_command_execution_span(self.r_obfuscation)
        assert span["resource"] == "echo"
        assert span["meta"]["cmd.exec"] == '["echo","password","?"]'
        assert span["meta"]["cmd.exit_code"] == "0"
