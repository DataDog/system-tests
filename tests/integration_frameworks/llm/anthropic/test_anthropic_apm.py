from utils import scenarios
from utils.docker_fixtures import FrameworkTestClientApi, TestAgentAPI

import pytest


# @features.apm_openai_completions
@scenarios.integration_frameworks_anthropic
class TestAnthropicApmCreate:
    @pytest.mark.parametrize("stream", [True, False])
    def test_create(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool):
        with test_agent.vcr_context():
            test_client.request(
                "POST",
                "/create",
                dict(
                    model="claude-3-7-sonnet-20250219",
                    messages=[
                        {"role": "user", "content": "What is 2+2?"},
                    ],
                    parameters=dict(
                        max_tokens=100,
                        temperature=0.5,
                        stream=stream,
                    ),
                ),
            )

        traces = test_agent.wait_for_num_traces(num=1)
        span = traces[0][0]

        assert span["name"] == "anthropic.request"
        assert span["resource"] == "Messages.create"
        assert span["meta"]["anthropic.request.model"] == "claude-3-7-sonnet-20250219"
