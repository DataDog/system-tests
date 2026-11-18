"""AI Guard <-> Anthropic client-managed MCP tests: tools converted with anthropic.lib.tools.mcp
(async_mcp_tool) from a real stdio MCP server are evaluated with their MCP server metadata. The
response evaluation references the server in tool_calls[].mcp.server_id and lists it in mcp_servers,
and running that tool_use afterwards is not evaluated again.

The cassettes were recorded through the test agent, with
./utils/scripts/generate-integration-framework-cassettes.sh --weblog anthropic-py@0.84.0 <this file>.
AI Guard cassettes are addressed by a hash of the exact evaluate request body: a tracer sending any
other body (messages, mcp.server_id or mcp_servers) misses them, the test agent answers with an HTTP
500 and AI Guard fails open, leaving the span without ai_guard.action. Every test asserts that each
evaluation matched, and that meta_struct.ai_guard reports the exact expected MCP metadata.

The weblog always starts the echo server with a secret marker in its env and extra args:
test_ai_guard_anthropic_mcp_tool_use asserts that it never reaches AI Guard.

Hand edit: the real backend allows the benign request of test_ai_guard_anthropic_mcp_response_blocked,
so the response of its response evaluation cassette (the one whose request has mcp_servers) was edited
to action DENY, is_blocking_enabled true and a reason. Its request was left as recorded.

A direct tool.call() with no preceding response evaluation is not covered: the tracer gives it a
random tool call ID, so its evaluate body cannot match a body-hashed cassette.
"""

import json
from typing import Any

import requests

from utils import pytest

from utils import features, scenarios
from utils.docker_fixtures import FrameworkTestClientApi, TestAgentAPI

from tests.integration_frameworks.llm.utils import (
    AI_GUARD_LIBRARY_ENV,
    SPANS_SETTLE_SECONDS,
    ai_guard_mcp_servers,
    ai_guard_messages,
    ai_guard_tool_calls,
    spans_named,
    wait_for_ai_guard_spans,
    wait_for_spans,
)
from .utils import TOOLS, BaseAnthropicTest


# Cross-tracer contract: "mcp_" + sha256(key).hexdigest()[:16], with
# key "stdio|python|integration_frameworks.mcp_echo_server" (command, then the module of python -m).
ECHO_SERVER_ID = "mcp_9d097fe19379c0dd"
# The mcp_servers entry of the weblog echo server: its env and extra args are never reported.
ECHO_SERVER: dict[str, Any] = {
    "id": ECHO_SERVER_ID,
    "managed_by": "client",
    "transport": "stdio",
    "command": "python",
    "args": ["integration_frameworks.mcp_echo_server"],
    "tools": {"echo": "echo"},
}
# Carried by the env and the extra args of the echo server in the weblog.
LEAK_MARKER = "s3cr3t"

# The cassettes were recorded for these requests: changing them makes the cassettes miss.
MODEL = "claude-sonnet-4-5-20250929"
PARAMETERS: dict[str, Any] = {"max_tokens": 200, "temperature": 0}
ECHO_TEXT = "hello from system-tests"
ECHO_PROMPT = f"Use the echo tool to echo exactly this text: {ECHO_TEXT}"
ECHO_AND_WEATHER_PROMPT = (
    f"In a single turn, call both tools in parallel: echo exactly this text: {ECHO_TEXT}, "
    "and get the weather in San Francisco, CA."
)
BLOCKED_PROMPT = "Use the echo tool to echo exactly this text: blocked by system-tests"
# Hand-edited into the response evaluation cassette of the blocked test.
BLOCKED_REASON = "system-tests: blocking DENY of the MCP tool call"


@pytest.fixture
def library_env() -> dict[str, str]:
    return dict(AI_GUARD_LIBRARY_ENV)


def _mcp_create(
    test_client: FrameworkTestClientApi,
    prompt: str,
    tools: list[dict[str, Any]] | None = None,
    *,
    raise_for_status: bool = True,
) -> requests.Response:
    return test_client.request(
        "POST",
        "/mcp/create",
        dict(model=MODEL, messages=[{"role": "user", "content": prompt}], parameters=PARAMETERS, tools=tools or []),
        raise_for_status=raise_for_status,
    )


def _anthropic_spans(test_agent: TestAgentAPI) -> list[dict[str, Any]]:
    return wait_for_spans(test_agent, lambda traces: spans_named(traces, "anthropic.request"), 1)


def _evaluations(
    test_agent: TestAgentAPI, mcp_servers: list[dict[str, Any]] | None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Assert exactly the prompt and the response evaluations happened and matched their cassettes, and
    that only the response evaluation reports mcp_servers. Returns every ai_guard span and the response one.
    """
    assert len(_anthropic_spans(test_agent)) == 1, "expected one anthropic.request span"
    # An evaluation from tool.call() has its own trace, which can arrive in a later flush: let it settle.
    spans = wait_for_ai_guard_spans(test_agent, 2, settle_seconds=SPANS_SETTLE_SECONDS)
    assert len(spans) == 2, f"expected the prompt and the response evaluations only, got {len(spans)} ai_guard spans"
    for span in spans:
        assert "ai_guard.action" in span["meta"], f"an AI Guard evaluation missed its cassette: {span['meta']}"
        assert ai_guard_messages(span), f"meta_struct.ai_guard.messages is missing: {span.get('meta_struct')}"

    by_target = {span["meta"]["ai_guard.target"]: span for span in spans}
    assert set(by_target) == {"prompt", "tool"}, f"unexpected evaluation targets: {list(by_target)}"
    assert ai_guard_mcp_servers(by_target["prompt"]) is None, "the prompt evaluation references no MCP server"
    assert ai_guard_mcp_servers(by_target["tool"]) == mcp_servers
    return spans, by_target["tool"]


def _tool_uses(response: dict[str, Any], name: str) -> list[dict[str, Any]]:
    return [block for block in response["response"]["content"] if block["type"] == "tool_use" and block["name"] == name]


def _assert_echo_call(span: dict[str, Any], response: dict[str, Any], mcp: dict[str, Any] | None) -> None:
    """The echo tool_use of the response is evaluated as is, with mcp when it is set."""
    (tool_use,) = _tool_uses(response, "echo")
    assert tool_use["input"] == {"text": ECHO_TEXT}
    (tool_call,) = ai_guard_tool_calls(span, "echo")
    assert tool_call["id"] == tool_use["id"]
    assert json.loads(tool_call["function"]["arguments"]) == tool_use["input"]
    if mcp is None:
        assert "mcp" not in tool_call
    else:
        assert tool_call["mcp"] == mcp
    # Run by the real MCP server.
    assert response["tool_results"] == [
        {"tool_use_id": tool_use["id"], "content": [{"type": "text", "text": ECHO_TEXT}]}
    ]


@features.ai_guard
@scenarios.integration_frameworks
class Test_AnthropicAiGuardMcp(BaseAnthropicTest):
    """Anthropic client-managed MCP tool calls are evaluated with their MCP server metadata."""

    def test_ai_guard_anthropic_mcp_tool_use(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi
    ) -> None:
        """The response evaluation references the stdio server, running its tool_use is not evaluated again,
        and the env and extra args of the server never reach AI Guard.
        """
        with test_agent.vcr_context():
            response = _mcp_create(test_client, ECHO_PROMPT).json()

        spans, span = _evaluations(test_agent, [ECHO_SERVER])
        assert span["meta"]["ai_guard.action"] == "ALLOW"
        _assert_echo_call(span, response, {"server_id": ECHO_SERVER_ID})
        for guard_span in spans:
            serialized = json.dumps({key: guard_span.get(key) for key in ("meta", "meta_struct", "metrics")})
            assert LEAK_MARKER not in serialized, f"a secret of the stdio server leaked into {serialized}"

    def test_ai_guard_anthropic_mcp_with_ordinary_tool(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi
    ) -> None:
        """An ordinary tool_use of the same response has no mcp field, and mcp_servers only lists the MCP server."""
        with test_agent.vcr_context():
            response = _mcp_create(test_client, ECHO_AND_WEATHER_PROMPT, TOOLS).json()

        _, span = _evaluations(test_agent, [ECHO_SERVER])
        _assert_echo_call(span, response, {"server_id": ECHO_SERVER_ID})
        (weather,) = ai_guard_tool_calls(span, "get_weather")
        assert "mcp" not in weather
        assert len(_tool_uses(response, "get_weather")) == 1

    def test_ai_guard_anthropic_mcp_response_blocked(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi
    ) -> None:
        """A blocking DENY of the response evaluation aborts messages.create, before the MCP tool runs."""
        with test_agent.vcr_context():
            status_code = _mcp_create(test_client, BLOCKED_PROMPT, raise_for_status=False).status_code
        # The weblog does not catch the AI Guard abort error, so the blocked call surfaces as a 500.
        assert status_code == 500, "expected the AI Guard abort to fail the /mcp/create call"

        _, span = _evaluations(test_agent, [ECHO_SERVER])
        assert span["meta"]["ai_guard.action"] == "DENY"
        assert span["meta"]["ai_guard.blocked"] == "true"
        assert span["meta"]["ai_guard.reason"] == BLOCKED_REASON
        (tool_call,) = ai_guard_tool_calls(span, "echo")
        assert tool_call["mcp"] == {"server_id": ECHO_SERVER_ID}

        (anthropic_span,) = _anthropic_spans(test_agent)
        assert "AIGuardAbortError" in anthropic_span["meta"].get("error.type", ""), anthropic_span["meta"]


@features.ai_guard
@scenarios.integration_frameworks
class Test_AnthropicAiGuardMcpDisabled(BaseAnthropicTest):
    """With DD_AI_GUARD_MCP_ENABLED=false, MCP tool calls are evaluated as ordinary tool calls."""

    @pytest.fixture
    def library_env(self) -> dict[str, str]:
        return {**AI_GUARD_LIBRARY_ENV, "DD_AI_GUARD_MCP_ENABLED": "false"}

    def test_ai_guard_anthropic_mcp_disabled(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi
    ) -> None:
        """No mcp field nor mcp_servers, and the tool_use runs with no extra evaluation.

        A regression guard for the kill-switch: a tracer without MCP support passes it too, the feature
        itself is covered by Test_AnthropicAiGuardMcp.
        """
        with test_agent.vcr_context():
            response = _mcp_create(test_client, ECHO_PROMPT).json()

        _, span = _evaluations(test_agent, None)
        _assert_echo_call(span, response, None)
