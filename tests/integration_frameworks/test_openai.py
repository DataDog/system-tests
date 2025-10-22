from utils import (
    context,
    missing_feature,
    scenarios,
)

import pytest

from tests.integration_frameworks.conftest import _TestAgentAPI
from utils.integration_frameworks._framework_client import FrameworkClient

@scenarios.integration_frameworks
class TestOpenAiAPM:
    @missing_feature(context.library == "nodejs", reason="Node.js openai server not implemented yet")
    @missing_feature(context.library == "java", reason="Java does not auto-instrument OpenAI")
    @pytest.mark.parametrize("stream", [True, False])
    def test_chat_completion(
        self, 
        test_agent: _TestAgentAPI, 
        test_client: FrameworkClient,
        stream: bool
    ):
        with test_agent.vcr_context():
            test_client.request("POST", "/chat/completions", dict(
                model="gpt-3.5-turbo",
                messages=[
                    dict(role="user", content="Hello OpenAI!")
                ],
                parameters=dict(
                    max_tokens=35,
                    stream=stream,
                )
            ))

        traces = test_agent.wait_for_num_traces(num=1)
        span = traces[0][0]

        assert span["name"] == "openai.request"
        assert span["resource"] == "createChatCompletion"
        assert span["meta"]["openai.request.model"] == "gpt-3.5-turbo"