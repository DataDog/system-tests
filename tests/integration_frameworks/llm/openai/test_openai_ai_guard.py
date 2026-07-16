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
import time

import pytest
import requests

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


def _ai_guard_event_root_spans(traces: list[list[dict]]) -> list[dict]:
    """Local root (service-entry) spans tagged ``ai_guard.event:true``.

    When AI Guard evaluates a call it tags the trace's local root span with
    ``ai_guard.event:true`` (dd-trace-py ``appsec/ai_guard/_api_client.py``). This is a
    tracer-emitted marker that AI Guard ran on the trace, and is what we assert on here.

    Note: the ``_dd.ai_guard.enabled:1`` facet that is searchable in the Datadog UI is NOT
    present in the raw payloads captured by the test agent (it is not emitted by the tracer;
    it is produced somewhere in intake), so it cannot be asserted on directly.
    """
    return [
        span
        for trace in traces
        for span in trace
        if span.get("parent_id") in (0, None) and span.get("meta", {}).get("ai_guard.event", False) in (True, "true")
    ]


def _wait_for_ai_guard_spans(
    test_agent: TestAgentAPI, *, target: str | None = None, wait_loops: int = 30
) -> list[dict]:
    """Poll the test agent until at least one matching ``ai_guard`` span is received.

    We assert on the presence of the ``ai_guard`` span rather than on a fixed number of
    traces: the tracer does not deterministically group the ``ai_guard`` span with the
    OpenAI span. In particular the streamed after-model evaluation may emit the
    ``ai_guard`` span either nested in the OpenAI trace (1 trace) or as its own trace
    (2 traces), so ``wait_for_num_traces`` with a hard-coded count is inherently racy.
    When ``target`` is given, only spans whose ``ai_guard.target`` matches are considered
    (so we keep polling until the specific evaluation point we care about has arrived).
    """
    spans: list[dict] = []
    for _ in range(wait_loops):
        try:
            traces = test_agent.traces(clear=False)
        except requests.exceptions.RequestException:
            pass
        else:
            spans = _ai_guard_spans(traces)
            if target is not None:
                spans = [span for span in spans if span["meta"].get("ai_guard.target") == target]
            if spans:
                return spans
        time.sleep(0.1)
    return spans


def _wait_for_ai_guard_event_root_spans(test_agent: TestAgentAPI, *, wait_loops: int = 30) -> list[dict]:
    """Poll the test agent until at least one root span tagged ``ai_guard.event:true`` arrives.

    Like the ``ai_guard`` span itself, the tagged local root span may land in a later trace
    chunk than the evaluation span, so we poll rather than reading a single snapshot.
    """
    spans: list[dict] = []
    for _ in range(wait_loops):
        try:
            traces = test_agent.traces(clear=False)
        except requests.exceptions.RequestException:
            pass
        else:
            spans = _ai_guard_event_root_spans(traces)
            if spans:
                return spans
        time.sleep(0.1)
    return spans


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

        guard_spans = _wait_for_ai_guard_spans(test_agent, target="prompt")
        assert guard_spans, "expected a before-model ai_guard span with target 'prompt'"

        event_root_spans = _wait_for_ai_guard_event_root_spans(test_agent)
        assert event_root_spans, "expected a local root span tagged ai_guard.event:true"

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

        guard_spans = _wait_for_ai_guard_spans(test_agent)
        assert guard_spans, "expected an ai_guard span from the after-model (streamed) evaluation"

        event_root_spans = _wait_for_ai_guard_event_root_spans(test_agent)
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

        guard_spans = _wait_for_ai_guard_spans(test_agent, target="tool")
        assert guard_spans, "expected a tool-call ai_guard span with target 'tool'"

        event_root_spans = _wait_for_ai_guard_event_root_spans(test_agent)
        assert event_root_spans, "expected a local root span tagged ai_guard.event:true"
