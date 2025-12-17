from utils import scenarios
from utils.docker_fixtures import FrameworkTestClientApi, TestAgentAPI

import pytest

from .utils import BaseGoogleGenaiTest


# TODO: add feature
@scenarios.integration_frameworks
class TestGoogleGenAiApm(BaseGoogleGenaiTest):
    @pytest.mark.parametrize("stream", [True, False])
    def test_generate_content(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/generate_content",
                body=dict(
                    model="gemini-2.0-flash",
                    contents="Why did the chicken cross the road?",
                    config=dict(
                        temperature=0.1,
                        max_output_tokens=50,
                        stream=stream,
                    ),
                ),
            )

        traces = test_agent.wait_for_num_traces(num=1)
        span = traces[0][0]

        resource = "Models.generate_content_stream" if stream else "Models.generate_content"

        assert span["name"] == "google_genai.request"
        assert span["resource"] == resource
        assert span["meta"]["google_genai.request.model"] == "gemini-2.0-flash"
        assert span["meta"]["google_genai.request.provider"] == "google"

    def test_embed_content(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        with test_agent.vcr_context():
            test_client.request(
                method="POST",
                url="/embed_content",
                body=dict(
                    model="gemini-embedding-001",
                    contents="Why did the chicken cross the road?",
                ),
            )

        traces = test_agent.wait_for_num_traces(num=1)
        span = traces[0][0]

        assert span["name"] == "google_genai.request"
        assert span["resource"] == "Models.embed_content"
        assert span["meta"]["google_genai.request.model"] == "gemini-embedding-001"
        assert span["meta"]["google_genai.request.provider"] == "google"
