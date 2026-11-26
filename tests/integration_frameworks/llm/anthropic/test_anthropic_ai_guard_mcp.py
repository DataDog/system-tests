"""AI Guard <-> Anthropic client-managed MCP tests: tools converted with anthropic.lib.tools.mcp
(async_mcp_tool) from a real stdio MCP server are checked when they run. messages.create is evaluated
as usual, its tool_use blocks as ordinary tool calls. Running an MCP tool is then evaluated as a lone
tool call that references its server in tool_calls[].mcp.server_id and lists it in mcp_servers.

The cassettes can be recorded through the test agent, with
./utils/scripts/generate-integration-framework-cassettes.sh --weblog anthropic-py@0.84.0 <this file>.
AI Guard cassettes are addressed by a hash of the exact evaluate request body: a tracer sending any
other body (messages, mcp.server_id or mcp_servers) misses them, the test agent answers with an HTTP
500 and AI Guard fails open, leaving the span without ai_guard.action. Every test asserts that each
evaluation matched, and that meta_struct.ai_guard reports the exact expected MCP metadata.

No tool_use ID reaches tool.call(), so the tracer gives the tool call of an MCP call evaluation a
random ID: the test agent of this module replaces it with a placeholder before hashing the body.

The weblog always starts the echo server with a secret marker in its env and extra args:
test_ai_guard_anthropic_mcp_tool_use asserts that it never reaches AI Guard.

Hand edit: the real backend allows the benign request of test_ai_guard_anthropic_mcp_call_blocked, so
the response of its MCP call evaluation cassette (the one whose request has mcp_servers) was edited to
action DENY, is_blocking_enabled true and a reason.
"""

import json
import re
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


# The ID only joins the tool call of an evaluation to its mcp_servers entry: the only server of its request.
ECHO_SERVER_ID = "mcp_1"
# The mcp_servers entry of the weblog echo server: its env and extra args are never reported.
ECHO_SERVER: dict[str, Any] = {
    "id": ECHO_SERVER_ID,
    "managed_by": "client",
    "transport": "stdio",
    "command": "python",
    "args": ["integration_frameworks.mcp_echo_server"],
    "tools": {"echo": "echo"},
}
# The random ID the tracer gives the tool call of an MCP call evaluation.
LOCAL_TOOL_CALL_ID = r"call_[0-9a-f]{32}"
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
BLOCKED_TEXT = "blocked by system-tests"
BLOCKED_PROMPT = f"Use the echo tool to echo exactly this text: {BLOCKED_TEXT}"
# Hand-edited into the MCP call evaluation cassette of the blocked test.
BLOCKED_REASON = "system-tests: blocking DENY of the MCP tool call"


@pytest.fixture
def library_env() -> dict[str, str]:
    return dict(AI_GUARD_LIBRARY_ENV)


@pytest.fixture
def agent_env() -> dict[str, str]:
    # Hash the request bodies without the random tool call ID, so the MCP call evaluations match their cassettes.
    return {"VCR_BODY_REGEX_NORMALIZERS": rf"\b{LOCAL_TOOL_CALL_ID}\b"}


def _mcp_create(
    test_client: FrameworkTestClientApi,
    prompt: str,
    tools: list[dict[str, Any]] | None = None,
    *,
    raise_for_status: bool = True,
    command_path: bool = False,
) -> requests.Response:
    body: dict[str, Any] = dict(
        model=MODEL, messages=[{"role": "user", "content": prompt}], parameters=PARAMETERS, tools=tools or []
    )
    if command_path:
        body["command_path"] = True
    return test_client.request("POST", "/mcp/create", body, raise_for_status=raise_for_status)


def _anthropic_spans(test_agent: TestAgentAPI, count: int = 1) -> list[dict[str, Any]]:
    return wait_for_spans(test_agent, lambda traces: spans_named(traces, "anthropic.request"), count)


def _evaluations(
    test_agent: TestAgentAPI, *, requests_count: int = 1, mcp_calls: int = 1
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Assert the prompt, the response and the MCP call evaluations of each request happened and matched their
    cassettes, and that only the MCP call evaluations report mcp_servers, the echo server.
    Returns every ai_guard span, the response evaluation spans and the MCP call evaluation spans.
    """
    anthropic_spans = _anthropic_spans(test_agent, requests_count)
    assert len(anthropic_spans) == requests_count, f"expected {requests_count} anthropic.request spans"
    expected = requests_count * (2 + mcp_calls)
    # Evaluations can land in their own traces and later flushes: let them settle, so an extra one is counted.
    spans = wait_for_ai_guard_spans(test_agent, expected, settle_seconds=SPANS_SETTLE_SECONDS)
    assert len(spans) == expected, f"expected {expected} ai_guard spans, got {len(spans)}"
    for span in spans:
        assert "ai_guard.action" in span["meta"], f"an AI Guard evaluation missed its cassette: {span['meta']}"
        assert ai_guard_messages(span), f"meta_struct.ai_guard.messages is missing: {span.get('meta_struct')}"

    prompt_spans = [span for span in spans if span["meta"]["ai_guard.target"] == "prompt"]
    tool_spans = [span for span in spans if span["meta"]["ai_guard.target"] == "tool"]
    # The response evaluation starts with the prompt, an MCP call evaluation is the tool call alone.
    response_spans = [span for span in tool_spans if ai_guard_messages(span)[0]["role"] == "user"]
    call_spans = [span for span in tool_spans if ai_guard_messages(span)[0]["role"] != "user"]
    assert len(prompt_spans) == requests_count, f"expected {requests_count} prompt evaluations"
    assert len(response_spans) == requests_count, f"expected {requests_count} response evaluations"
    assert len(call_spans) == requests_count * mcp_calls, f"expected {requests_count * mcp_calls} MCP call evaluations"
    for span in prompt_spans + response_spans:
        assert ai_guard_mcp_servers(span) is None, "only the MCP call evaluations reference an MCP server"
    for span in call_spans:
        assert ai_guard_mcp_servers(span) == [ECHO_SERVER]
    return spans, response_spans, call_spans


def _tool_uses(response: dict[str, Any], name: str) -> list[dict[str, Any]]:
    return [block for block in response["response"]["content"] if block["type"] == "tool_use" and block["name"] == name]


def _assert_echo_response(span: dict[str, Any], response: dict[str, Any]) -> None:
    """The echo tool_use of the response is evaluated as is, as an ordinary tool call."""
    (tool_use,) = _tool_uses(response, "echo")
    (tool_call,) = ai_guard_tool_calls(span, "echo")
    assert tool_call["id"] == tool_use["id"]
    assert json.loads(tool_call["function"]["arguments"]) == tool_use["input"]
    assert "mcp" not in tool_call


def _assert_echo_call(span: dict[str, Any], text: str = ECHO_TEXT) -> None:
    """Running the echo tool is evaluated as a lone tool call that references the echo server."""
    (message,) = ai_guard_messages(span)
    assert message["role"] == "assistant"
    (tool_call,) = message["tool_calls"]
    assert re.fullmatch(LOCAL_TOOL_CALL_ID, tool_call["id"]), tool_call["id"]
    assert tool_call["function"]["name"] == "echo"
    assert json.loads(tool_call["function"]["arguments"]) == {"text": text}
    assert tool_call["mcp"] == {"server_id": ECHO_SERVER_ID}


def _assert_echo_ran(response: dict[str, Any]) -> None:
    """The real MCP server ran the echo tool_use."""
    (tool_use,) = _tool_uses(response, "echo")
    assert tool_use["input"] == {"text": ECHO_TEXT}
    assert response["tool_results"] == [
        {"tool_use_id": tool_use["id"], "content": [{"type": "text", "text": ECHO_TEXT}]}
    ]


@features.ai_guard
@scenarios.integration_frameworks
class Test_AnthropicAiGuardMcp(BaseAnthropicTest):
    """Anthropic client-managed MCP tool calls are evaluated with their MCP server metadata when they run."""

    def test_ai_guard_anthropic_mcp_tool_use(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi
    ) -> None:
        """The response evaluation sees the tool_use as an ordinary tool call, running it is evaluated with the
        stdio server, and the env and extra args of the server never reach AI Guard.
        """
        with test_agent.vcr_context():
            response = _mcp_create(test_client, ECHO_PROMPT).json()

        spans, (response_span,), (call_span,) = _evaluations(test_agent)
        _assert_echo_response(response_span, response)
        assert call_span["meta"]["ai_guard.action"] == "ALLOW"
        _assert_echo_call(call_span)
        _assert_echo_ran(response)
        for guard_span in spans:
            serialized = json.dumps({key: guard_span.get(key) for key in ("meta", "meta_struct", "metrics")})
            assert LEAK_MARKER not in serialized, f"a secret of the stdio server leaked into {serialized}"

    def test_ai_guard_anthropic_mcp_with_ordinary_tool(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi
    ) -> None:
        """An ordinary tool_use of the same response has no mcp field, and only the MCP tool call is evaluated
        when it runs.
        """
        with test_agent.vcr_context():
            response = _mcp_create(test_client, ECHO_AND_WEATHER_PROMPT, TOOLS).json()

        _, (response_span,), (call_span,) = _evaluations(test_agent)
        _assert_echo_response(response_span, response)
        (weather,) = ai_guard_tool_calls(response_span, "get_weather")
        assert "mcp" not in weather
        assert len(_tool_uses(response, "get_weather")) == 1
        _assert_echo_call(call_span)
        _assert_echo_ran(response)

    def test_ai_guard_anthropic_mcp_reconnect_same_server_id(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi
    ) -> None:
        """Each request spawns a new stdio server and opens a new MCP session, and the MCP call evaluation of
        each one reports the server of its own session, with the same entry and ID.
        """
        with test_agent.vcr_context():
            responses = [_mcp_create(test_client, ECHO_PROMPT).json() for _ in range(2)]

        _, response_spans, call_spans = _evaluations(test_agent, requests_count=2)
        for span, response in zip(response_spans, responses, strict=True):
            _assert_echo_response(span, response)
        for span in call_spans:
            _assert_echo_call(span)

    def test_ai_guard_anthropic_mcp_command_path(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi
    ) -> None:
        """A stdio server started from an absolute path is reported with its program name only: the path can
        hold a user name and changes from machine to machine, so it never reaches AI Guard.
        """
        with test_agent.vcr_context():
            response = _mcp_create(test_client, ECHO_PROMPT, command_path=True).json()

        # The MCP call evaluation cassette matches only when mcp_servers carries command "python".
        spans, _, (call_span,) = _evaluations(test_agent)
        _assert_echo_call(call_span)
        _assert_echo_ran(response)
        for guard_span in spans:
            assert "/python" not in json.dumps(guard_span.get("meta_struct")), "the command path reached AI Guard"

    def test_ai_guard_anthropic_mcp_call_blocked(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi
    ) -> None:
        """A blocking DENY of the MCP call evaluation aborts the tool call, after messages.create completed."""
        with test_agent.vcr_context():
            status_code = _mcp_create(test_client, BLOCKED_PROMPT, raise_for_status=False).status_code
        # The weblog does not catch the AI Guard abort error, so the blocked call surfaces as a 500.
        assert status_code == 500, "expected the AI Guard abort to fail the /mcp/create call"

        _, (response_span,), (call_span,) = _evaluations(test_agent)
        assert response_span["meta"]["ai_guard.action"] == "ALLOW"
        assert call_span["meta"]["ai_guard.action"] == "DENY"
        assert call_span["meta"]["ai_guard.blocked"] == "true"
        assert call_span["meta"]["ai_guard.reason"] == BLOCKED_REASON
        _assert_echo_call(call_span, BLOCKED_TEXT)

        (anthropic_span,) = _anthropic_spans(test_agent)
        assert "error.type" not in anthropic_span["meta"], anthropic_span["meta"]


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

        _, (response_span,), _ = _evaluations(test_agent, mcp_calls=0)
        _assert_echo_response(response_span, response)
        _assert_echo_ran(response)
