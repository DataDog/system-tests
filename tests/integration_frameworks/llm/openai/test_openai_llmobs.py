import json
from utils import context, features, missing_feature, scenarios

import pytest
from unittest import mock

from utils.docker_fixtures import FrameworkTestClientApi, TestAgentAPI
from tests.integration_frameworks.llm.utils import assert_llmobs_span_event, assert_prompt_tracking


from .utils import TOOLS, BaseOpenaiTest


@pytest.fixture
def library_env() -> dict[str, str]:
    return {
        "DD_LLMOBS_ENABLED": "true",
        "DD_LLMOBS_ML_APP": "test-app",
    }


def tool_to_tool_definition(tool: dict) -> dict:
    function = tool["function"]
    return {
        "name": function["name"],
        "description": function["description"],
        "schema": function["parameters"],
    }


@features.llm_observability_openai_llm_interactions
@scenarios.integration_frameworks
class TestOpenAiLlmInteractions(BaseOpenaiTest):
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

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]

        expected_metadata: dict = {
            "max_tokens": 35,
            "stream": stream,
        }

        if stream:
            expected_metadata["stream_options"] = {"include_usage": True}

        assert_llmobs_span_event(
            llm_span_event,
            integration="openai",
            name="OpenAI.createChatCompletion",
            model_name="gpt-3.5-turbo-0125",
            model_provider="openai",
            span_kind="llm",
            input_messages=[{"role": "user", "content": "Hello OpenAI!"}],
            output_messages=[{"role": "assistant", "content": "Hello! How can I assist you today?"}],
            metadata=expected_metadata,
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
                "cache_read_input_tokens": mock.ANY,
                "reasoning_output_tokens": mock.ANY,
            },
        )

    @pytest.mark.parametrize("stream", [True, False])
    def test_chat_completion_error(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                "POST",
                "/chat/completions",
                dict(
                    model="gpt-3.5-turbo-instruct",  # using a bad model
                    messages=[dict(role="user", content="Hello OpenAI!")],
                    parameters=dict(
                        max_tokens=35,
                        stream=stream,
                    ),
                ),
                raise_for_status=False,  # we expect an error
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        expected_metadata: dict = {
            "max_tokens": 35,
            "stream": stream,
        }

        if stream:
            expected_metadata["stream_options"] = {"include_usage": True}

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="openai",
            name="OpenAI.createChatCompletion",
            model_name="gpt-3.5-turbo-instruct",  # should use input model name for error
            model_provider="openai",
            span_kind="llm",
            input_messages=[{"role": "user", "content": "Hello OpenAI!"}],
            metadata=expected_metadata,
            error=True,
            ignore_values=["meta.output.messages"],
        )

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

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="openai",
            name="OpenAI.createCompletion",
            model_name="gpt-3.5-turbo-instruct:20230824-v2",
            model_provider="openai",
            span_kind="llm",
            input_messages=[{"role": "", "content": "Hello OpenAI!"}],
            output_messages=[{"role": "", "content": "\n\nHello there! What can I assist you with?"}],
            metadata={"max_tokens": 35},
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
            },
        )

    def test_completion_error(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        with test_agent.vcr_context():
            test_client.request(
                "POST",
                "/completions",
                dict(
                    model="gpt-3.5-turbo",  # using a bad model
                    prompt="Hello OpenAI!",
                    parameters=dict(
                        max_tokens=35,
                    ),
                ),
                raise_for_status=False,  # we expect an error
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="openai",
            name="OpenAI.createCompletion",
            model_name="gpt-3.5-turbo",  # should use input model name for error
            model_provider="openai",
            span_kind="llm",
            input_messages=[{"role": "", "content": "Hello OpenAI!"}],
            metadata={"max_tokens": 35},
            error=True,
            ignore_values=["meta.output.messages"],
        )

    @missing_feature(
        context.library == "nodejs",
        reason="Node.js LLM Observability OpenAI integration does not submit tool definitions",
    )
    @pytest.mark.parametrize("stream", [True, False])
    def test_chat_completion_tool_call(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
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

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        expected_metadata: dict = {
            "tool_choice": "auto",
            "stream": stream,
        }

        if stream:
            expected_metadata["stream_options"] = {"include_usage": True}

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="openai",
            name="OpenAI.createChatCompletion",
            model_name="gpt-3.5-turbo-0125",
            model_provider="openai",
            span_kind="llm",
            input_messages=[
                {"role": "user", "content": "Bob is a student at Stanford University. He is studying computer science."}
            ],
            output_messages=[
                {
                    "content": "",
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "name": "extract_student_info",
                            "arguments": {
                                "name": "Bob",
                                "major": "computer science",
                                "school": "Stanford University",
                            },
                            "tool_id": mock.ANY,
                            "type": "function",
                        }
                    ],
                }
            ],
            tool_definitions=[tool_to_tool_definition(TOOLS[0])],
            metadata=expected_metadata,
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
                "cache_read_input_tokens": mock.ANY,
                "reasoning_output_tokens": mock.ANY,
            },
        )

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

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        if stream:
            expected_output = "Ah, ya lookin’ for a Dunkies, huh? Classic! In Boston, ya can’t throw a rock without hittin’ a Dunkin’. Just head down the street, take a left at the rotary, and ya should see one"  # noqa: RUF001
        else:
            expected_output = "Ah, ya lookin’ for a Dunkin’, huh? Classic! In Boston, ya can’t throw a rock without hittin’ a Dunkin’ Donuts. There’s prob’ly one on the next street ovah, right next"  # noqa: RUF001

        llm_span_event = span_events[0]

        assert_llmobs_span_event(
            llm_span_event,
            integration="openai",
            name="OpenAI.createResponse",
            model_name="gpt-4.1-2025-04-14",
            model_provider="openai",
            span_kind="llm",
            input_messages=[
                {"role": "system", "content": "Talk with a Boston accent."},
                {"role": "user", "content": "Where is the nearest Dunkin' Donuts?"},
            ],
            output_messages=[{"role": "assistant", "content": expected_output}],
            metadata={
                "max_output_tokens": 50,
                "temperature": 0.1,
                "top_p": 1.0,
                "tool_choice": "auto",
                "truncation": "disabled",
                "text": {"format": {"type": "text"}, "verbosity": "medium"},
                "stream": stream,
            },
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
                "cache_read_input_tokens": mock.ANY,
                "reasoning_output_tokens": mock.ANY,
            },
        )

    @pytest.mark.parametrize("stream", [True, False])
    def test_responses_create_error(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                "POST",
                "/responses/create",
                dict(
                    model="gpt-amazing-model-doesnt-exist-1.0",  # using a bad model
                    input="Where is the nearest Dunkin' Donuts?",
                    parameters=dict(
                        max_output_tokens=50, temperature=0.1, stream=stream, instructions="Talk with a Boston accent."
                    ),
                ),
                raise_for_status=False,  # we expect an error
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="openai",
            name="OpenAI.createResponse",
            model_name="gpt-amazing-model-doesnt-exist-1.0",  # should use input model name for error
            model_provider="openai",
            span_kind="llm",
            input_messages=[
                {"role": "system", "content": "Talk with a Boston accent."},
                {"role": "user", "content": "Where is the nearest Dunkin' Donuts?"},
            ],
            metadata=mock.ANY,
            error=True,
            ignore_values=["meta.output.messages"],
        )

    @missing_feature(
        context.library == "nodejs",
        reason="Node.js LLM Observability OpenAI integration does not submit tool definitions",
    )
    @pytest.mark.parametrize("stream", [True, False])
    def test_responses_create_tool_call(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                "POST",
                "/responses/create",
                dict(
                    model="gpt-4.1",
                    input="Bob is a student at Stanford University. He is studying computer science.",
                    parameters=dict(
                        max_output_tokens=50,
                        temperature=0.1,
                        stream=stream,
                        tools=[{"type": "function", **TOOLS[0]["function"]}],  # different format for responses tools
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="openai",
            name="OpenAI.createResponse",
            model_name="gpt-4.1-2025-04-14",
            model_provider="openai",
            span_kind="llm",
            input_messages=[
                {"role": "user", "content": "Bob is a student at Stanford University. He is studying computer science."}
            ],
            output_messages=[
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "name": "extract_student_info",
                            "arguments": {
                                "name": "Bob",
                                "major": "computer science",
                                "school": "Stanford University",
                            },
                            "tool_id": mock.ANY,
                            "type": "function_call",
                        }
                    ],
                }
            ],
            tool_definitions=[tool_to_tool_definition(TOOLS[0])],
            metadata={
                "max_output_tokens": 50,
                "temperature": 0.1,
                "top_p": 1.0,
                "tool_choice": "auto",
                "truncation": "disabled",
                "text": {"format": {"type": "text"}, "verbosity": "medium"},
                "stream": stream,
            },
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
                "cache_read_input_tokens": mock.ANY,
                "reasoning_output_tokens": mock.ANY,
            },
        )

    @pytest.mark.parametrize("stream", [True, False])
    def test_responses_create_reasoning(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                "POST",
                "/responses/create",
                dict(
                    model="o4-mini",
                    input="If one plus a number is 10, what is the number?",
                    parameters=dict(reasoning={"effort": "medium", "summary": "detailed"}, stream=stream),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]

        if stream:
            expected_assistant_output = "The number is 9, since 1 + x = 10 ⇒ x = 10 − 1 = 9."  # noqa: RUF001
        else:
            expected_assistant_output = "The number is 9, since 1 + x = 10 implies x = 10 − 1 = 9."  # noqa: RUF001

        assert_llmobs_span_event(
            llm_span_event,
            integration="openai",
            name="OpenAI.createResponse",
            model_name="o4-mini-2025-04-16",
            model_provider="openai",
            span_kind="llm",
            input_messages=[{"role": "user", "content": "If one plus a number is 10, what is the number?"}],
            output_messages=[
                {"role": "reasoning", "content": mock.ANY},
                {"role": "assistant", "content": expected_assistant_output},
            ],
            metadata=dict(
                reasoning={"effort": "medium", "summary": "detailed"},
                temperature=1.0,
                top_p=1.0,
                tool_choice="auto",
                truncation="disabled",
                text={"format": {"type": "text"}, "verbosity": "medium"},
                stream=stream,
            ),
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
                "cache_read_input_tokens": mock.ANY,
                "reasoning_output_tokens": 64,
            },
        )

        assert json.loads(llm_span_event["meta"]["output"]["messages"][0]["content"]) == {
            "summary": [],
            "encrypted_content": None,
            "id": "rs_01cc995e72aafb3301691629ccc508819fa65e0ba65aa355b7"
            if stream
            else "rs_0c11158be1f235a601691629d64884819e8c24cf7e973aa7aa",
        }

    @pytest.mark.parametrize("stream", [True, False])
    def test_responses_create_tool_input(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        input_messages = [
            {"role": "user", "content": "What's the weather like in San Francisco?"},
            {
                "type": "function_call",
                "call_id": "call_123",
                "name": "get_weather",
                "arguments": '{"location": "San Francisco, CA"}',
            },
            {
                "type": "function_call_output",
                "call_id": "call_123",
                "output": '{"temperature": "72°F", "conditions": "sunny", "humidity": "65%"}',
            },
        ]

        with test_agent.vcr_context(stream=stream):
            test_client.request(
                "POST",
                "/responses/create",
                dict(
                    model="gpt-4.1",
                    input=input_messages,
                    parameters=dict(temperature=0.1, stream=stream),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        expected_metadata = dict(
            temperature=0.1,
            top_p=1.0,
            tool_choice="auto",
            truncation="disabled",
            text={"format": {"type": "text"}, "verbosity": "medium"},
            stream=stream,
        )

        if stream:
            expected_output = "The current weather in San Francisco is sunny with a temperature of 72°F and a humidity level of 65%. Let me know if you need a forecast or more details!"
        else:
            expected_output = "The current weather in San Francisco is sunny with a temperature of 72°F and a humidity level of 65%. Let me know if you need a forecast for the next few days or more details!"

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="openai",
            name="OpenAI.createResponse",
            model_name="gpt-4.1-2025-04-14",
            model_provider="openai",
            span_kind="llm",
            input_messages=[
                {"role": "user", "content": "What's the weather like in San Francisco?"},
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "tool_id": "call_123",
                            "name": "get_weather",
                            "arguments": {"location": "San Francisco, CA"},
                            "type": "function_call",
                        }
                    ],
                },
                {
                    "role": "user",
                    "tool_results": [
                        {
                            "tool_id": "call_123",
                            "result": '{"temperature": "72°F", "conditions": "sunny", "humidity": "65%"}',
                            "type": "function_call_output",
                            "name": "",  # since it was omitted above in the input
                        }
                    ],
                },
            ],
            output_messages=[
                {"role": "assistant", "content": expected_output},
            ],
            metadata=expected_metadata,
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
                "cache_read_input_tokens": mock.ANY,
                "reasoning_output_tokens": mock.ANY,
            },
        )


@features.llm_observability_openai_embeddings
@scenarios.integration_frameworks
class TestOpenAiEmbeddingInteractions(BaseOpenaiTest):
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

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="openai",
            name="OpenAI.createEmbedding",
            model_name="text-embedding-ada-002-v2",
            model_provider="openai",
            span_kind="embedding",
            input_messages=None,
            input_documents=[{"text": "Hello OpenAI!"}],
            output_value="[1 embedding(s) returned with size 1536]",
            metadata={"encoding_format": "float"},
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
                "reasoning_output_tokens": mock.ANY,
            },
        )

    def test_embedding_error(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        with test_agent.vcr_context():
            test_client.request(
                "POST",
                "/embeddings",
                dict(
                    model="text-embedding-ada-001",  # using a bad model
                    input="Hello OpenAI!",
                ),
                raise_for_status=False,  # we expect an error
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="openai",
            name="OpenAI.createEmbedding",
            model_name="text-embedding-ada-001",  # should use input model name for error
            model_provider="openai",
            input_documents=[{"text": "Hello OpenAI!"}],
            span_kind="embedding",
            metadata=mock.ANY,
            error=True,
            has_output=False,
        )


@features.llm_observability_prompts
@scenarios.integration_frameworks
class TestOpenAiPromptTracking(BaseOpenaiTest):
    """Tests for OpenAI reusable prompt tracking (reverse templating).

    These tests validate that prompt templates with {{variable}} placeholders
    are correctly reconstructed from OpenAI's rendered responses.

    Test prompts are on Datadog Staging OpenAI dashboard - do not modify them.
    """

    def test_responses_create_with_prompt_overlapping_values(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi
    ):
        """Test prompt tracking with overlapping variable values (longest-first matching)."""
        with test_agent.vcr_context():
            test_client.request(
                "POST",
                "/responses/create",
                dict(
                    parameters=dict(
                        prompt={
                            "id": "pmpt_6911a8b8f7648197b39bd62127a696910d4a05830d5ba1e6",
                            "version": "1",
                            "variables": {"phrase": "cat in the hat", "word": "cat"},
                        },
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        assert_prompt_tracking(
            span_events[0],
            prompt_id="pmpt_6911a8b8f7648197b39bd62127a696910d4a05830d5ba1e6",
            prompt_version="1",
            variables={"phrase": "cat in the hat", "word": "cat"},
            expected_chat_template=[{"role": "user", "content": "I saw a {{phrase}} and another {{word}}"}],
            expected_messages=[{"role": "user", "content": "I saw a cat in the hat and another cat"}],
        )

    def test_responses_create_with_prompt_partial_word_match(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi
    ):
        """Test prompt tracking with partial word matches and multiple roles."""
        with test_agent.vcr_context():
            test_client.request(
                "POST",
                "/responses/create",
                dict(
                    parameters=dict(
                        prompt={
                            "id": "pmpt_6911a954c8988190a82b11560faa47cd0d6629899573dd8f",
                            "version": "2",
                            "variables": {"word": "test"},
                        },
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        assert_prompt_tracking(
            span_events[0],
            prompt_id="pmpt_6911a954c8988190a82b11560faa47cd0d6629899573dd8f",
            prompt_version="2",
            variables={"word": "test"},
            expected_chat_template=[
                {"role": "developer", "content": 'Reply with "OK".'},
                {
                    "role": "user",
                    "content": "This is a {{word}} for {{word}}ing the {{word}}er",
                },
            ],
            expected_messages=[
                {"role": "developer", "content": 'Reply with "OK".'},
                {"role": "user", "content": "This is a test for testing the tester"},
            ],
        )

    def test_responses_create_with_prompt_special_characters(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi
    ):
        """Test prompt tracking with special characters in variable values."""
        with test_agent.vcr_context():
            test_client.request(
                "POST",
                "/responses/create",
                dict(
                    parameters=dict(
                        prompt={
                            "id": "pmpt_6911a99a3eec81959d5f2e408a2654380b2b15731a51f191",
                            "version": "2",
                            "variables": {"price": "$99.99", "item": "groceries"},
                        },
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        assert_prompt_tracking(
            span_events[0],
            prompt_id="pmpt_6911a99a3eec81959d5f2e408a2654380b2b15731a51f191",
            prompt_version="2",
            variables={"price": "$99.99", "item": "groceries"},
            expected_chat_template=[{"role": "user", "content": "The price of {{item}} is {{price}}."}],
            expected_messages=[{"role": "user", "content": "The price of groceries is $99.99."}],
        )

    def test_responses_create_with_prompt_empty_values(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi
    ):
        """Test prompt tracking with empty variable values (should be skipped)."""
        with test_agent.vcr_context():
            test_client.request(
                "POST",
                "/responses/create",
                dict(
                    parameters=dict(
                        prompt={
                            "id": "pmpt_6911a8b8f7648197b39bd62127a696910d4a05830d5ba1e6",
                            "version": "1",
                            "variables": {"phrase": "cat in the hat", "word": ""},
                        },
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        assert_prompt_tracking(
            span_events[0],
            prompt_id="pmpt_6911a8b8f7648197b39bd62127a696910d4a05830d5ba1e6",
            prompt_version="1",
            variables={"phrase": "cat in the hat", "word": ""},
            expected_chat_template=[{"role": "user", "content": "I saw a {{phrase}} and another "}],
            expected_messages=[{"role": "user", "content": "I saw a cat in the hat and another "}],
        )

    def test_responses_create_with_prompt_mixed_inputs_url_stripped(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi
    ):
        """Test mixed input types (text, image, file) - default behavior where image_url is stripped."""
        with test_agent.vcr_context():
            test_client.request(
                "POST",
                "/responses/create",
                dict(
                    parameters=dict(
                        prompt={
                            "id": "pmpt_69201db75c4c81959c01ea6987ab023c070192cd2843dec0",
                            "version": "2",
                            "variables": {
                                "user_message": {
                                    "type": "input_text",
                                    "text": "Analyze these images and document",
                                },
                                "user_image_1": {
                                    "type": "input_image",
                                    "image_url": "https://raw.githubusercontent.com/github/explore/main/topics/python/python.png",
                                    "detail": "auto",
                                },
                                "user_file": {
                                    "type": "input_file",
                                    "file_url": "https://www.berkshirehathaway.com/letters/2024ltr.pdf",
                                },
                                "user_image_2": {
                                    "type": "input_image",
                                    "file_id": "file-BCuhT1HQ24kmtsuuzF1mh2",
                                    "detail": "auto",
                                },
                            },
                        },
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        assert_prompt_tracking(
            span_events[0],
            prompt_id="pmpt_69201db75c4c81959c01ea6987ab023c070192cd2843dec0",
            prompt_version="2",
            variables={
                "user_message": "Analyze these images and document",
                "user_image_1": "https://raw.githubusercontent.com/github/explore/main/topics/python/python.png",
                "user_file": "https://www.berkshirehathaway.com/letters/2024ltr.pdf",
                "user_image_2": "file-BCuhT1HQ24kmtsuuzF1mh2",
            },
            expected_chat_template=[
                {
                    "role": "user",
                    "content": (
                        "Analyze the following content from the user:\n\n"
                        "Text message: {{user_message}}\n"
                        "Image reference 1: [image]\n"
                        "Document reference: {{user_file}}\n"
                        "Image reference 2: {{user_image_2}}\n\n"
                        "Please provide a comprehensive analysis."
                    ),
                }
            ],
            expected_messages=[
                {
                    "role": "user",
                    "content": (
                        "Analyze the following content from the user:\n\n"
                        "Text message: Analyze these images and document\n"
                        "Image reference 1: [image]\n"
                        "Document reference: https://www.berkshirehathaway.com/letters/2024ltr.pdf\n"
                        "Image reference 2: file-BCuhT1HQ24kmtsuuzF1mh2\n\n"
                        "Please provide a comprehensive analysis."
                    ),
                }
            ],
        )

    def test_responses_create_with_prompt_mixed_inputs_url_preserved(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi
    ):
        """Test mixed input types (text, image, file) - with include param to preserve image_url."""
        with test_agent.vcr_context():
            test_client.request(
                "POST",
                "/responses/create",
                dict(
                    parameters=dict(
                        prompt={
                            "id": "pmpt_69201db75c4c81959c01ea6987ab023c070192cd2843dec0",
                            "version": "2",
                            "variables": {
                                "user_message": {
                                    "type": "input_text",
                                    "text": "Analyze these images and document",
                                },
                                "user_image_1": {
                                    "type": "input_image",
                                    "image_url": "https://raw.githubusercontent.com/github/explore/main/topics/python/python.png",
                                    "detail": "auto",
                                },
                                "user_file": {
                                    "type": "input_file",
                                    "file_url": "https://www.berkshirehathaway.com/letters/2024ltr.pdf",
                                },
                                "user_image_2": {
                                    "type": "input_image",
                                    "file_id": "file-BCuhT1HQ24kmtsuuzF1mh2",
                                    "detail": "auto",
                                },
                            },
                        },
                        include=["message.input_image.image_url"],
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        assert_prompt_tracking(
            span_events[0],
            prompt_id="pmpt_69201db75c4c81959c01ea6987ab023c070192cd2843dec0",
            prompt_version="2",
            variables={
                "user_message": "Analyze these images and document",
                "user_image_1": "https://raw.githubusercontent.com/github/explore/main/topics/python/python.png",
                "user_file": "https://www.berkshirehathaway.com/letters/2024ltr.pdf",
                "user_image_2": "file-BCuhT1HQ24kmtsuuzF1mh2",
            },
            expected_chat_template=[
                {
                    "role": "user",
                    "content": (
                        "Analyze the following content from the user:\n\n"
                        "Text message: {{user_message}}\n"
                        "Image reference 1: {{user_image_1}}\n"
                        "Document reference: {{user_file}}\n"
                        "Image reference 2: {{user_image_2}}\n\n"
                        "Please provide a comprehensive analysis."
                    ),
                }
            ],
            expected_messages=[
                {
                    "role": "user",
                    "content": (
                        "Analyze the following content from the user:\n\n"
                        "Text message: Analyze these images and document\n"
                        "Image reference 1: https://raw.githubusercontent.com/github/explore/main/topics/python/python.png\n"
                        "Document reference: https://www.berkshirehathaway.com/letters/2024ltr.pdf\n"
                        "Image reference 2: file-BCuhT1HQ24kmtsuuzF1mh2\n\n"
                        "Please provide a comprehensive analysis."
                    ),
                }
            ],
        )
