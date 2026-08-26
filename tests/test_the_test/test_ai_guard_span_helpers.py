"""Unit tests for the AI Guard span assertions used by the INTEGRATION_FRAMEWORKS suites.

The span shapes they tolerate (parent_id absent vs 0, ai_guard.event bool vs string) differ per library.
"""

import re
from typing import Any

import pytest
import requests

from tests.integration_frameworks.llm import utils as llm_utils
from tests.integration_frameworks.llm.utils import (
    assert_ai_guard_evaluated,
    assert_assistant_tool_calls_forwarded,
)


pytestmark = pytest.mark.scenario("TEST_THE_TEST")

TOOL_CALL_MESSAGES = [{"role": "assistant", "tool_calls": [{"name": "get_weather"}]}]
EVENT_ROOT_SPAN = {"parent_id": 0, "meta": {"ai_guard.event": True}}


def _guard_span(target: str = "prompt", messages: list[dict] | None = None) -> dict[str, Any]:
    span: dict[str, Any] = {"resource": "ai_guard", "meta": {"ai_guard.target": target}}
    if messages is not None:
        span["meta_struct"] = {"ai_guard": {"messages": messages}}
    return span


class _FakeTestAgent:
    """Returns each queued item in turn from traces(); queued exceptions are raised instead."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = responses
        self.calls = 0

    def traces(self, *, clear: bool = False) -> Any:  # noqa: ANN401, ARG002
        self.calls += 1
        response = self._responses[min(self.calls - 1, len(self._responses) - 1)]
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the give-up paths (30 poll loops) from actually sleeping for 3 seconds."""
    monkeypatch.setattr(llm_utils.time, "sleep", lambda _: None)


def test_only_the_ai_guard_spans_for_the_requested_target_are_returned() -> None:
    tool_span = _guard_span("tool")
    agent = _FakeTestAgent(
        [
            [
                [{"resource": "anthropic.request", "meta": {}}, _guard_span("prompt")],
                [tool_span, EVENT_ROOT_SPAN],
            ]
        ]
    )

    assert assert_ai_guard_evaluated(agent, target="tool") == [tool_span]  # type: ignore[arg-type]


def test_fails_when_no_ai_guard_span_matches_the_target() -> None:
    agent = _FakeTestAgent([[[_guard_span("prompt"), EVENT_ROOT_SPAN]]])

    with pytest.raises(AssertionError, match="ai_guard span with target 'tool'"):
        assert_ai_guard_evaluated(agent, target="tool")  # type: ignore[arg-type]


@pytest.mark.parametrize("parent_id", [0, None])
@pytest.mark.parametrize("event_value", [True, "true"])
def test_every_root_span_serialisation_is_accepted(parent_id: Any, event_value: Any) -> None:  # noqa: ANN401
    root = {"parent_id": parent_id, "meta": {"ai_guard.event": event_value}}
    agent = _FakeTestAgent([[[_guard_span("prompt"), root]]])

    assert assert_ai_guard_evaluated(agent, target="prompt")  # type: ignore[arg-type]


def test_root_span_without_parent_id_is_accepted() -> None:
    agent = _FakeTestAgent([[[_guard_span("prompt"), {"meta": {"ai_guard.event": "true"}}]]])

    assert assert_ai_guard_evaluated(agent, target="prompt")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "root_span",
    [
        pytest.param({"parent_id": 42, "meta": {"ai_guard.event": True}}, id="tagged-but-not-a-local-root"),
        pytest.param({"parent_id": 0, "meta": {}}, id="untagged"),
        pytest.param({"parent_id": 0, "meta": {"ai_guard.event": False}}, id="explicitly-false"),
    ],
)
def test_fails_when_no_local_root_span_carries_the_event_tag(root_span: dict) -> None:
    agent = _FakeTestAgent([[[_guard_span("prompt"), root_span]]])

    with pytest.raises(AssertionError, match=re.escape("ai_guard.event:true")):
        assert_ai_guard_evaluated(agent, target="prompt")  # type: ignore[arg-type]


def test_polls_until_the_spans_arrive_and_tolerates_a_down_test_agent() -> None:
    agent = _FakeTestAgent(
        [
            requests.exceptions.ConnectionError("test agent not up yet"),
            [[_guard_span("prompt")]],
            [[_guard_span("prompt"), _guard_span("tool"), EVENT_ROOT_SPAN]],
        ]
    )

    assert assert_ai_guard_evaluated(agent, target="tool") == [_guard_span("tool")]  # type: ignore[arg-type]
    # it consumed the connection error and the snapshot that had no tool span before succeeding
    assert agent.calls >= 3


def test_assistant_tool_calls_are_required_in_the_evaluation_payload() -> None:
    assert_assistant_tool_calls_forwarded([_guard_span("tool", TOOL_CALL_MESSAGES)])


@pytest.mark.parametrize(
    "messages",
    [
        pytest.param(None, id="no-meta-struct"),
        pytest.param([], id="no-messages"),
        pytest.param([{"role": "user", "content": "hi"}], id="user-turn-only"),
        pytest.param([{"role": "assistant", "content": "hi"}], id="assistant-turn-without-tool-calls"),
    ],
)
def test_fails_when_the_assistant_tool_calls_entry_is_missing(messages: list[dict] | None) -> None:
    with pytest.raises(AssertionError, match="assistant tool_calls entry"):
        assert_assistant_tool_calls_forwarded([_guard_span("tool", messages)])
