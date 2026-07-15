"""AI Guard <-> OpenAI integration tests, run under the INTEGRATION_FRAMEWORKS scenario.

Investigation task: https://datadoghq.atlassian.net/browse/APPSEC-68977

Unlike ``tests/ai_guard/test_ai_guard_sdk.py`` (which drives the AI Guard SDK directly via
``/ai_guard/evaluate``), this suite exercises the *integration* between AI Guard and the
OpenAI client, the same way the LLM Observability suite does: it calls the OpenAI SDK
directly through the existing weblog endpoints (``/chat/completions``). When
``DD_AI_GUARD_ENABLED=true``, ``ai_guard_listen()`` auto-wires into the OpenAI SDK, so AI
Guard evaluates the call at three points with no manual ``evaluate()`` call:

- **before-model**: the request/prompt is evaluated before the model is called;
- **after-model**: the model response is evaluated (streamed responses require
  ``DD_AI_GUARD_ANALYZE_STREAM_RESPONSES_ENABLED=true``, which buffers and reconstructs
  the response before running the evaluation);
- **tool-call**: tool calls produced by the model are evaluated.

We assert only that the integration wires each evaluation point and emits an ``ai_guard``
span attached to the OpenAI trace. The evaluation *outcome* (ALLOW / DENY / ABORT) is
already covered by the ``AI_GUARD`` scenario and is intentionally not re-asserted here.
"""

import os

import pytest

from utils import features, scenarios
from utils.docker_fixtures import FrameworkTestClientApi, TestAgentAPI

from .utils import TOOLS, BaseOpenaiTest


@pytest.fixture
def library_env(request: pytest.FixtureRequest) -> dict[str, str]:
    env = {
        "DD_AI_GUARD_ENABLED": "true",
        # after-model evaluation of streamed responses is opt-in
        "DD_AI_GUARD_ANALYZE_STREAM_RESPONSES_ENABLED": "true",
    }
    # The AI Guard client needs an API key + app key. Real keys are required when recording
    # cassettes (the client calls the real AI Guard API); mock keys are fine on replay since
    # the VCR proxy matches on the request, not on auth.
    if request.config.option.generate_cassettes:
        env["DD_API_KEY"] = os.environ["DD_API_KEY"]
        env["DD_APP_KEY"] = os.environ["DD_APP_KEY"]
    else:
        env["DD_API_KEY"] = "mock_api_key"
        env["DD_APP_KEY"] = "mock_app_key"
    return env


def _ai_guard_spans(traces: list[list[dict]]) -> list[dict]:
    return [span for trace in traces for span in trace if span.get("resource") == "ai_guard"]


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

        guard_spans = _ai_guard_spans(test_agent.wait_for_num_traces(num=1))
        assert guard_spans, "expected an ai_guard span from the before-model evaluation"
        assert any(span["meta"].get("ai_guard.target") == "prompt" for span in guard_spans), (
            "expected a before-model ai_guard span with target 'prompt'"
        )

    def test_after_model_validation(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        """The streamed model response is evaluated by AI Guard after the model returns."""
        with test_agent.vcr_context(stream=True):
            test_client.request(
                "POST",
                "/chat/completions",
                dict(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": "Tell me a short story about a robot."}],
                    parameters=dict(max_tokens=35, stream=True),
                ),
            )

        guard_spans = _ai_guard_spans(test_agent.wait_for_num_traces(num=2))
        assert guard_spans, "expected an ai_guard span from the after-model (streamed) evaluation"

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

        guard_spans = _ai_guard_spans(test_agent.wait_for_num_traces(num=1))
        assert guard_spans, "expected an ai_guard span from the tool-call evaluation"
        assert any(span["meta"].get("ai_guard.target") == "tool" for span in guard_spans), (
            "expected a tool-call ai_guard span with target 'tool'"
        )
