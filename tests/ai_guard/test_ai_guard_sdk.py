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
    def _assert_span(self, action: str, *, blocking: bool):
        evaluated_messages = MESSAGES[action]

        def validate(span: dict):
            if span["resource"] != "ai_guard":
                return False

            # 1. main meta tags
            meta = span["meta"]
            _assert_key(meta, "ai_guard.action", action)
            _assert_key(meta, "ai_guard.reason")
            target = "prompt" if evaluated_messages[-1]["role"] == "user" else "tool"
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
            messages = _assert_key(ai_guard, "messages")
            assert messages == evaluated_messages, "Invalid messages stored in the meta struct"
            if action != "ALLOW" and blocking:
                assert span["error"] == 1
                assert meta["ai_guard.blocked"] == "true", f"'ai_guard.blocked' with value 'true' not found in '{meta}'"
                assert "AIGuardAbortError".lower() in meta["error.type"].lower()

            return True

        return validate

    def setup_non_blocking_allow(self):
        self.r = weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: "false"}, json=MESSAGES["ALLOW"])

    def test_non_blocking_allow(self):
        assert self.r.status_code == 200
        interfaces.library.validate_one_span(
            self.r, validator=self._assert_span(action="ALLOW", blocking=False), full_trace=True
        )

    def setup_non_blocking_deny(self):
        self.r = weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: "false"}, json=MESSAGES["DENY"])

    def test_non_blocking_deny(self):
        assert self.r.status_code == 200
        interfaces.library.validate_one_span(
            self.r, validator=self._assert_span(action="DENY", blocking=False), full_trace=True
        )

    def setup_non_blocking_abort(self):
        self.r = weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: "false"}, json=MESSAGES["ABORT"])

    def test_non_blocking_abort(self):
        assert self.r.status_code == 200
        interfaces.library.validate_one_span(
            self.r, validator=self._assert_span(action="ABORT", blocking=False), full_trace=True
        )

    def setup_blocking_allow(self):
        self.r = weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: "true"}, json=MESSAGES["ALLOW"])

    def test_blocking_allow(self):
        assert self.r.status_code == 200
        interfaces.library.validate_one_span(
            self.r, validator=self._assert_span(action="ALLOW", blocking=True), full_trace=True
        )

    def setup_blocking_deny(self):
        self.r = weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: "true"}, json=MESSAGES["DENY"])

    def test_blocking_deny(self):
        assert self.r.status_code == 403
        interfaces.library.validate_one_span(
            self.r, validator=self._assert_span(action="DENY", blocking=True), full_trace=True
        )

    def setup_blocking_abort(self):
        self.r = weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: "true"}, json=MESSAGES["ABORT"])

    def test_blocking_abort(self):
        assert self.r.status_code == 403
        interfaces.library.validate_one_span(
            self.r, validator=self._assert_span(action="ABORT", blocking=True), full_trace=True
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
        self.r = weblog.post("/ai_guard/evaluate", json=MESSAGES["DENY"])

    def test_evaluation(self):
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        interfaces.library.validate_one_span(
            self.r, validator=self._assert_span(response=body, action="DENY"), full_trace=True
        )
