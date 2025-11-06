from utils import scenarios, features

import pytest
import os

from utils.docker_fixtures import FrameworkTestClientApi, TestAgentAPI


@pytest.fixture
def library_env() -> dict[str, str]:
    """Pass on the real API key for cassette generation for new tests."""

    return {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "<not-a-real-key>"),
    }


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "extract_student_info",
            "description": "Get the student information from the body of the input text",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the person"},
                    "major": {"type": "string", "description": "Major subject."},
                    "school": {
                        "type": "string",
                        "description": "The university name.",
                    },
                },
            },
        },
    }
]


@features.llm_observability
@scenarios.integration_frameworks
class TestOpenAiAPM:
    @pytest.mark.parametrize("stream", [True, False])
    def test_chat_completion(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                "POST",
                "/chat/completions",
                dict(
                    model="gpt-3.5-turbo",
                    messages=[dict(role="user", content="Hello OpenAI!")],
                    parameters=dict(
                        max_tokens=35,
                        stream=stream,
                    ),
                ),
            )

        traces = test_agent.wait_for_num_traces(num=1)
        span = traces[0][0]

        assert span["name"] == "openai.request"
        assert span["resource"] in ("createChatCompletion", "chat.completions.create")
        assert span["meta"]["openai.request.model"] == "gpt-3.5-turbo"

    def test_completion(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        with test_agent.vcr_context():
            test_client.request(
                "POST",
                "/completions",
                dict(
                    model="gpt-3.5-turbo-instruct",
                    prompt="Hello OpenAI!",
                    parameters=dict(
                        max_tokens=35,
                    ),
                ),
            )

        traces = test_agent.wait_for_num_traces(num=1)
        span = traces[0][0]

        assert span["name"] == "openai.request"
        assert span["resource"] in ("createCompletion", "completions.create")
        assert span["meta"]["openai.request.model"] == "gpt-3.5-turbo-instruct"

    def test_embedding(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        with test_agent.vcr_context():
            test_client.request(
                "POST",
                "/embeddings",
                dict(
                    model="text-embedding-ada-002",
                    input="Hello OpenAI!",
                ),
            )

        traces = test_agent.wait_for_num_traces(num=1)
        span = traces[0][0]

        assert span["name"] == "openai.request"
        assert span["resource"] in ("createEmbedding", "embeddings.create")
        assert span["meta"]["openai.request.model"] == "text-embedding-ada-002"

    @pytest.mark.parametrize("stream", [True, False])
    def test_chat_completion_tool_call(
        self,
        test_client: FrameworkTestClientApi,
        test_agent: TestAgentAPI,
        *,
        stream: bool,
    ):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                "POST",
                "/chat/completions",
                dict(
                    messages=[
                        dict(
                            role="user",
                            content="Bob is a student at Stanford University. He is studying computer science.",
                        )
                    ],
                    model="gpt-3.5-turbo",
                    parameters={
                        "stream": stream,
                        "tool_choice": "auto",
                        "tools": TOOLS,
                    },
                ),
            )

        traces = test_agent.wait_for_num_traces(num=1)
        span = traces[0][0]

        assert span["name"] == "openai.request"
        assert span["resource"] in ("chat.completions.create", "createChatCompletion")
        assert span["meta"]["openai.request.model"] == "gpt-3.5-turbo"

    @pytest.mark.parametrize("stream", [True, False])
    def test_responses_create(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                "POST",
                "/responses/create",
                dict(
                    model="gpt-4.1",
                    input="Where is the nearest Dunkin' Donuts?",
                    parameters=dict(
                        max_output_tokens=50, temperature=0.1, stream=stream, instructions="Talk with a Boston accent."
                    ),
                ),
            )

        traces = test_agent.wait_for_num_traces(num=1)
        span = traces[0][0]

        assert span["name"] == "openai.request"
        assert span["resource"] in ("responses.create", "createResponse")
        assert span["meta"]["openai.request.model"] == "gpt-4.1"
