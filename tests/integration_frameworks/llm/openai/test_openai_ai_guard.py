"""AI Guard <-> OpenAI integration tests (APPSEC-68977): DD_AI_GUARD_ENABLED=true auto-evaluates the
/chat/completions request and its tool calls. After-model needs the stream path: not yet cross-language.
"""

from utils import pytest

from utils import features, scenarios
from utils.docker_fixtures import FrameworkTestClientApi, TestAgentAPI

from tests.integration_frameworks.llm.utils import (
    AI_GUARD_LIBRARY_ENV,
    assert_ai_guard_evaluated,
    assert_assistant_tool_calls_forwarded,
)
from .utils import TOOLS, BaseOpenaiTest


@pytest.fixture
def library_env() -> dict[str, str]:
    return dict(AI_GUARD_LIBRARY_ENV)


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

        assert_ai_guard_evaluated(test_agent, target="prompt")

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

        guard_spans = assert_ai_guard_evaluated(test_agent, target="tool")
        assert_assistant_tool_calls_forwarded(guard_spans)
