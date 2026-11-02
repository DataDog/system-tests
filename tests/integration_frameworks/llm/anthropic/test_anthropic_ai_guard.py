"""AI Guard <-> Anthropic integration tests (APPSEC-68977): DD_AI_GUARD_ENABLED=true auto-evaluates the
/create request and its tool_use blocks. After-model needs the stream path: not yet cross-language.
"""

from utils import pytest

from utils import features, scenarios
from utils.docker_fixtures import FrameworkTestClientApi, TestAgentAPI

from tests.integration_frameworks.llm.utils import (
    AI_GUARD_LIBRARY_ENV,
    assert_ai_guard_evaluated,
    assert_assistant_tool_calls_forwarded,
)
from .utils import TOOLS, BaseAnthropicTest


@pytest.fixture
def library_env() -> dict[str, str]:
    return dict(AI_GUARD_LIBRARY_ENV)


@features.ai_guard
@scenarios.integration_frameworks
class TestAnthropicAiGuard(BaseAnthropicTest):
    """AI Guard evaluation triggered through the auto-instrumented Anthropic integration."""

    def test_before_model_validation(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        """The prompt is evaluated by AI Guard before the Anthropic model is called."""
        with test_agent.vcr_context():
            test_client.request(
                "POST",
                "/create",
                dict(
                    model="claude-sonnet-4-5-20250929",
                    messages=[{"role": "user", "content": "What is 2+2?"}],
                    parameters=dict(max_tokens=100, temperature=0.5, stream=False),
                ),
            )

        assert_ai_guard_evaluated(test_agent, target="prompt")

    def test_tool_call_validation(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        """Tool calls produced by the model are evaluated by AI Guard."""
        with test_agent.vcr_context():
            test_client.request(
                "POST",
                "/create",
                dict(
                    model="claude-sonnet-4-5-20250929",
                    messages=[{"role": "user", "content": "What is the weather in New York City?"}],
                    parameters=dict(max_tokens=100, temperature=0.5, stream=False, tools=TOOLS),
                ),
            )

        guard_spans = assert_ai_guard_evaluated(test_agent, target="tool")
        assert_assistant_tool_calls_forwarded(guard_spans)
