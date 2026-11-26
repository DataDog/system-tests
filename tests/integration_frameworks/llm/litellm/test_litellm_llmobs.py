from __future__ import annotations

from typing import Any, TYPE_CHECKING
from unittest import mock

from tests.integration_frameworks.llm.utils import LlmObsSpanEvent, assert_llmobs_span_event
from utils import features, pytest, scenarios

from .utils import BaseLitellmTest, assert_gateway_marker, span_kind, wait_for_llmobs_span_events

if TYPE_CHECKING:
    from utils import FrameworkTestClientApi, TestAgentAPI


MODEL = "gpt-4o-mini"
CONTENT = "What is 2+2? Answer with one word."
MESSAGES = [{"role": "user", "content": CONTENT}]
ANSWER = "Four."

# The weblog path and the request body of each litellm operation. All of them send the same request to OpenAI.
OPERATIONS: dict[str, tuple[str, dict[str, Any]]] = {
    "completion": ("/chat/completions", {"messages": MESSAGES}),
    "acompletion": ("/chat/completions", {"messages": MESSAGES, "use_async": True}),
    "text_completion": ("/completions", {"prompt": CONTENT}),
    "router.completion": ("/chat/completions", {"messages": MESSAGES, "use_router": True}),
    "router.acompletion": ("/chat/completions", {"messages": MESSAGES, "use_router": True, "use_async": True}),
}


@pytest.fixture
def library_env() -> dict[str, str]:
    return {
        "DD_LLMOBS_ENABLED": "true",
        "DD_LLMOBS_ML_APP": "test-app",
    }


def _call(
    test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, operation: str, *, stream: bool, proxied: bool
) -> list[LlmObsSpanEvent]:
    """Do the litellm operation, and return the span events: the router workflow span if any, then the llm span."""
    path, body = OPERATIONS[operation]
    with test_agent.vcr_context("test_litellm", stream=stream):
        test_client.request(
            "POST",
            path,
            dict(model=MODEL, parameters=dict(max_tokens=10, stream=stream), proxied=proxied, **body),
        )

    expected_kinds = ["workflow", "llm"] if body.get("use_router") else ["llm"]
    span_events = wait_for_llmobs_span_events(test_agent, num=len(expected_kinds))
    assert [span_kind(span_event) for span_event in span_events] == expected_kinds
    return span_events


@features.llm_observability_litellm_gateway
@scenarios.integration_frameworks
class TestLitellmLlmObsGateway(BaseLitellmTest):
    """The LiteLLM proxy server gives proxy_server_request to litellm. Then the llm span has the gateway marker."""

    @pytest.mark.parametrize("proxied", [True, False])
    @pytest.mark.parametrize("operation", list(OPERATIONS))
    def test_streamed(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, operation: str, proxied: bool
    ):
        """In a streamed call, the litellm integration makes the llm span."""
        span_events = _call(test_agent, test_client, operation, stream=True, proxied=proxied)

        assert_gateway_marker(span_events, expected="litellm" if proxied else None)
        # The litellm integration does not record the roles of a text completion.
        is_text = operation == "text_completion"
        assert_llmobs_span_event(
            span_events[-1],
            name=operation.removeprefix("router."),
            span_kind="llm",
            integration="litellm",
            model_name=MODEL,
            model_provider="openai",
            input_messages=[{"role": "" if is_text else "user", "content": CONTENT}],
            output_messages=[{"role": "" if is_text else "assistant", "content": ANSWER}],
            metadata={"max_tokens": 10, "stream": True},
            metrics=mock.ANY,
        )

    @pytest.mark.parametrize("proxied", [True, False])
    @pytest.mark.parametrize("operation", list(OPERATIONS))
    def test_not_streamed(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, operation: str, proxied: bool
    ):
        """In a call that is not streamed, the OpenAI integration makes the llm span, below the litellm call."""
        span_events = _call(test_agent, test_client, operation, stream=False, proxied=proxied)

        assert_gateway_marker(span_events, expected="litellm" if proxied else None)
        assert_llmobs_span_event(
            span_events[-1],
            name="OpenAI.createChatCompletion",
            span_kind="llm",
            integration="openai",
            model_name=mock.ANY,
            model_provider="openai",
            input_messages=MESSAGES,
            output_messages=[{"role": "assistant", "content": ANSWER}],
            metadata={"max_tokens": 10},
            metrics=mock.ANY,
        )
