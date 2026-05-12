from utils import context, scenarios, features
from utils.docker_fixtures import FrameworkTestClientApi, TestAgentAPI

import pytest

from .utils import BaseAnthropicTest


@features.apm_anthropic_messages
@scenarios.integration_frameworks
class TestAnthropicApmMessages(BaseAnthropicTest):
    @pytest.mark.parametrize("stream", [True, False])
    def test_create(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/create",
                body=dict(
                    model="claude-sonnet-4-5-20250929",
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
        assert span["meta"]["anthropic.request.model"] == "claude-sonnet-4-5-20250929"

    def test_create_stream_method(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        with test_agent.vcr_context():
            test_client.request(
                method="POST",
                url="/stream",
                body=dict(
                    model="claude-sonnet-4-5-20250929",
                    messages=[
                        {"role": "user", "content": "What is 2+2?"},
                    ],
                    parameters=dict(
                        max_tokens=100,
                        temperature=0.5,
                    ),
                ),
            )

        traces = test_agent.wait_for_num_traces(num=1)
        span = traces[0][0]

        assert span["name"] == "anthropic.request"
        # nodejs does not patch the stream method directly, so it still shows up as create
        assert span["resource"] == "Messages.create" if context.library == "nodejs" else "Messages.stream"
        assert span["meta"]["anthropic.request.model"] == "claude-sonnet-4-5-20250929"
