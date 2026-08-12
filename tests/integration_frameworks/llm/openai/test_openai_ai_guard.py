"""AI Guard <-> OpenAI integration tests, run under the INTEGRATION_FRAMEWORKS scenario.

Investigation task: https://datadoghq.atlassian.net/browse/APPSEC-68977

Unlike ``tests/ai_guard/test_ai_guard_sdk.py`` (which drives the AI Guard SDK directly via
``/ai_guard/evaluate``), this suite exercises the *integration* between AI Guard and the
OpenAI client, the same way the LLM Observability suite does: it calls the OpenAI SDK
directly through the existing weblog endpoints (``/chat/completions``). When
``DD_AI_GUARD_ENABLED=true``, ``ai_guard_listen()`` auto-wires into the OpenAI SDK, so AI
Guard evaluates the call at three points with no manual ``evaluate()`` call:

- **before-model**: the request/prompt is evaluated before the model is called;
- **tool-call**: tool calls produced by the model are evaluated.

The after-model evaluation is intentionally not covered here: exercising it end-to-end needs
the streamed-response path (``DD_AI_GUARD_ANALYZE_STREAM_RESPONSES_ENABLED``), which is not
implemented across the other tracer libraries yet, so we keep this suite at cross-language
parity.

We assert that the integration wires each evaluation point: that it emits an ``ai_guard``
span for the specific evaluation being exercised (identified by ``ai_guard.target`` and by
the messages captured in ``meta_struct.ai_guard``) and tags the local root span with
``ai_guard.event:true``. We do not assert trace *linkage* to the ``openai.request`` span:
the tracer does not deterministically nest the ``ai_guard`` span in the OpenAI trace (it
may be emitted as its own trace), so a shared ``trace_id`` is not guaranteed. The
evaluation *outcome* (ALLOW / DENY / ABORT) is already covered by the ``AI_GUARD`` scenario
and is intentionally not re-asserted here.
"""

import pytest

from utils import features, scenarios
from utils.docker_fixtures import FrameworkTestClientApi, TestAgentAPI

from tests.integration_frameworks.llm.utils import (
    guard_messages,
    wait_for_ai_guard_event_root_spans,
    wait_for_ai_guard_spans,
)
from .utils import TOOLS, BaseOpenaiTest


@pytest.fixture
def library_env() -> dict[str, str]:
    # The AI Guard client also needs DD_API_KEY / DD_APP_KEY, but those are injected via the
    # scenario environment (see IntegrationFrameworksScenario._required_cassette_generation_api_keys)
    # rather than here: library_env is copied into the JSON report metadata, so keeping secrets
    # out of it prevents real keys from leaking into logs/artifacts during cassette generation.
    return {
        "DD_AI_GUARD_ENABLED": "true",
    }


@features.ai_guard
@scenarios.integration_frameworks
class TestOpenAiAiGuard(BaseOpenaiTest):
    """AI Guard evaluation triggered through the auto-instrumented OpenAI integration."""

    def test_before_model_validation(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        """The prompt is evaluated by AI Guard before the OpenAI model is called."""
        with test_agent.vcr_context():
            test_client.request(
                "POST",
                "/chat/completions",
                dict(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": "What is the weather like today?"}],
                    parameters=dict(max_tokens=35),
                ),
            )

        guard_spans = wait_for_ai_guard_spans(test_agent, target="prompt")
        assert guard_spans, "expected a before-model ai_guard span with target 'prompt'"

        event_root_spans = wait_for_ai_guard_event_root_spans(test_agent)
        assert event_root_spans, "expected a local root span tagged ai_guard.event:true"

    def test_tool_call_validation(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        """Tool calls produced by the model are evaluated by AI Guard."""
        with test_agent.vcr_context():
            test_client.request(
                "POST",
                "/chat/completions",
                dict(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "user",
                            "content": "Bob is a student at Stanford University. He is studying computer science.",
                        }
                    ],
                    parameters=dict(tool_choice="auto", tools=TOOLS),
                ),
            )

        guard_spans = wait_for_ai_guard_spans(test_agent, target="tool")
        assert guard_spans, "expected a tool-call ai_guard span with target 'tool'"
        # ``target == "tool"`` alone can also come from an ordinary after-model eval of an
        # assistant response, so require the assistant tool_calls entry to actually be in the
        # payload sent to AI Guard - that is what proves the tool-call path was forwarded.
        assert any(
            msg.get("role") == "assistant" and msg.get("tool_calls")
            for span in guard_spans
            for msg in guard_messages(span)
        ), "expected the assistant tool_calls entry in the ai_guard evaluation payload"

        event_root_spans = wait_for_ai_guard_event_root_spans(test_agent)
        assert event_root_spans, "expected a local root span tagged ai_guard.event:true"
