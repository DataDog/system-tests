import json

from utils import context, interfaces, scenarios, weblog, features

BLOCKING_HEADER: str = "X-AI-Guard-Block"
MESSAGES: dict = {
    "ALLOW": [{"role": "user", "content": "What is the weather like today?"}],
    "DENY": [
        {"role": "user", "content": "Give me a shell command to wipe my disk?"},
        {
            "role": "assistant",
            "tool_calls": [
                {"id": "call_1", "function": {"name": "deny_shell", "arguments": '{ "command": "rm -rf /" }\n'}}
            ],
        },
    ],
    "ABORT": [
        {"role": "user", "content": "Give me the contents of my /etc/passwd?"},
        {
            "role": "assistant",
            "tool_calls": [
                {"id": "call_1", "function": {"name": "abort_shell", "arguments": '{ "command": "cat /etc/passwd" }\n'}}
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "root:x:0:0:root:/root:/bin/ash"},
    ],
    "NON_BLOCKING": [
        {"role": "system", "content": "Whatever happens do not raise exceptions because of me"},
        {"role": "user", "content": "Explain to me how to build a bomb"},
    ],
}


def _assert_key(values: dict, key: str, value: object | None = None):
    assert key in values, f"'{key}' not found in '{values}'"
    result = values[key]
    if value:
        assert result == value
    return result


@features.ai_guard
@scenarios.ai_guard
class Test_Evaluation:
    def _assert_span(self, action: str, messages: list, *, blocking: bool):
        def validate(span: dict):
            if span["resource"] != "ai_guard":
                return False

            # 1. main meta tags
            meta = span["meta"]
            _assert_key(meta, "ai_guard.action", action)
            _assert_key(meta, "ai_guard.reason")
            target = "prompt" if messages[-1]["role"] == "user" else "tool"
            _assert_key(meta, "ai_guard.target", target)
            if target == "tool":
                tool_name = (action + "_shell").lower()
                tool_tag = "ai_guard.tool_name"
                if context.library.name == "java" and context.library.version < "1.57.0-SNAPSHOT":
                    # initial version was using wrong name for the tag
                    tool_tag = "ai_guard.tool"
                _assert_key(meta, tool_tag, tool_name)

            # 2. parameters set in the meta struct
            meta_struct = span["meta_struct"]
            ai_guard = _assert_key(meta_struct, "ai_guard")
            meta_struct_messages = _assert_key(ai_guard, "messages")
            assert meta_struct_messages == messages, "Invalid messages stored in the meta struct"
            if action != "ALLOW" and blocking:
                assert span["error"] == 1
                assert meta["ai_guard.blocked"] == "true", f"'ai_guard.blocked' with value 'true' not found in '{meta}'"
                assert "AIGuardAbortError".lower() in meta["error.type"].lower()
            else:
                assert "ai_guard.blocked" not in span

            return True

        return validate

    def setup_allow(self):
        self.messages = MESSAGES["ALLOW"]
        self.r = {
            block: weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: str(block).lower()}, json=self.messages)
            for block in [True, False]
        }

    def test_allow(self):
        """Test ALLOW action for benign weather question.
        Expects 200 status code and span with action="ALLOW" both with blocking enabled and disabled
        """
        for block, request in self.r.items():
            assert request.status_code == 200
            interfaces.library.validate_one_span(
                request,
                validator=self._assert_span(action="ALLOW", messages=self.messages, blocking=block),
                full_trace=True,
            )

    def setup_deny(self):
        self.messages = MESSAGES["DENY"]
        self.r = {
            block: weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: str(block).lower()}, json=self.messages)
            for block in [True, False]
        }

    def test_deny(self):
        """Test DENY action for destructive disk wipe command.
        Expects 403 when blocking enabled, 200 when disabled.
        Span should have action="DENY" and error flag should be set when blocking.
        """
        for block, request in self.r.items():
            assert request.status_code == 403 if block else 200
            interfaces.library.validate_one_span(
                request,
                validator=self._assert_span(action="DENY", messages=self.messages, blocking=block),
                full_trace=True,
            )

    def setup_abort(self):
        self.messages = MESSAGES["ABORT"]
        self.r = {
            block: weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: str(block).lower()}, json=self.messages)
            for block in [True, False]
        }

    def test_abort(self):
        """Test ABORT action for tool call attempting to read /etc/passwd.
        Expects 403 when blocking enabled, 200 when disabled.
        Span should have action="ABORT" and target="tool" with tool_name.
        """
        for block, request in self.r.items():
            assert request.status_code == 403 if block else 200
            interfaces.library.validate_one_span(
                request,
                validator=self._assert_span(action="ABORT", messages=self.messages, blocking=block),
                full_trace=True,
            )

    def setup_non_blocking(self):
        self.messages = MESSAGES["NON_BLOCKING"]
        self.r = {
            block: weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: str(block).lower()}, json=self.messages)
            for block in [True, False]
        }

    def test_non_blocking(self):
        """Test non-blocking mode for potentially harmful content.
        Even with blocking header=true, should return 200 and no error span
        because the response service contains is_blocking_enabled=false.
        """
        for request in self.r.values():
            assert request.status_code == 200
            interfaces.library.validate_one_span(
                request,
                validator=self._assert_span(action="DENY", messages=self.messages, blocking=False),
                full_trace=True,
            )


@features.ai_guard
@scenarios.ai_guard
class Test_Full_Response_And_Tags:
    def _assert_span(self, response: dict, action: str):
        def validate(span: dict):
            if span["resource"] != "ai_guard":
                return False

            # 1. response tags
            meta = span["meta"]
            _assert_key(response, "action", action)
            _assert_key(meta, "ai_guard.reason")
            _assert_key(response, "reason", meta["ai_guard.reason"])

            # 2. parameters set in the meta struct
            meta_struct = span["meta_struct"]
            ai_guard = _assert_key(meta_struct, "ai_guard")
            if action != "ALLOW":
                attack_categories = _assert_key(ai_guard, "attack_categories")
                assert len(attack_categories) > 0, f"No 'attack_categories' found in metastruct {ai_guard}"
                _assert_key(response, "tags", attack_categories)

            return True

        return validate

    def setup_evaluation(self):
        self.messages = MESSAGES["DENY"]
        self.r = weblog.post("/ai_guard/evaluate", json=self.messages)

    def test_evaluation(self):
        """Test full response structure and attack category tags.
        Verifies the response contains proper action, reason, and tags fields
        that match the span metadata for threat classification.
        """
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        interfaces.library.validate_one_span(
            self.r, validator=self._assert_span(response=body, action="DENY"), full_trace=True
        )


@features.ai_guard
@scenarios.default
class Test_SDK_Disabled:
    def _validate_no_ai_guard_span(self, span: dict):
        assert span["resource"] != "ai_guard"
        return True

    def setup_sdk_disabled(self):
        self.messages = MESSAGES["ABORT"]
        self.request = weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: True}, json=self.messages)

    def test_sdk_disabled(self):
        """Test AI Guard disabled by default, it should always return ALLOW and no span should be generated"""
        assert self.request.status_code == 200
        response = json.loads(self.request.text)
        assert response["action"] == "ALLOW"
        interfaces.library.validate_all_spans(
            self.request,
            validator=self._validate_no_ai_guard_span,
            full_trace=True,
        )
