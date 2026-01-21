from tests.integration_frameworks.llm.utils import assert_llmobs_span_event
from utils import bug, context, features, missing_feature, scenarios
from utils.docker_fixtures import FrameworkTestClientApi, TestAgentAPI

from .utils import BaseAnthropicTest

import pytest
from unittest import mock
import json

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get the current weather in a given location",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA",
                }
            },
            "required": ["location"],
        },
    }
]


@pytest.fixture
def library_env() -> dict[str, str]:
    return {
        "DD_LLMOBS_ENABLED": "true",
        "DD_LLMOBS_ML_APP": "test-app",
    }


@features.llm_observability_anthropic_messages
@scenarios.integration_frameworks
class TestAnthropicLlmObsMessages(BaseAnthropicTest):
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

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        expected_output = "2 + 2 = 4" if stream else "2+2 = 4"

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="anthropic",
            name="anthropic.request",
            model_name="claude-sonnet-4-5-20250929",
            model_provider="anthropic",
            span_kind="llm",
            input_messages=[{"role": "user", "content": "What is 2+2?"}],
            output_messages=[{"role": "assistant", "content": expected_output}],
            metadata={
                "max_tokens": 100,
                "temperature": 0.5,
            },
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
                "cache_read_input_tokens": mock.ANY,
                "cache_write_input_tokens": mock.ANY,
            },
        )

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

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="anthropic",
            name="anthropic.request",
            model_name="claude-sonnet-4-5-20250929",
            model_provider="anthropic",
            span_kind="llm",
            input_messages=[{"role": "user", "content": "What is 2+2?"}],
            output_messages=[{"role": "assistant", "content": "2+2 = 4"}],
            metadata={
                "max_tokens": 100,
                "temperature": 0.5,
            },
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
                "cache_read_input_tokens": mock.ANY,
                "cache_write_input_tokens": mock.ANY,
            },
        )

    @pytest.mark.parametrize("stream", [True, False])
    def test_create_content_block(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/create",
                body=dict(
                    model="claude-sonnet-4-5-20250929",
                    messages=[
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": "How many ships are there in the fleet?"}],
                        }
                    ],
                    parameters=dict(
                        system="You are a helpful assistant who speaks like a pirate.",
                        max_tokens=100,
                        temperature=0.5,
                        stream=stream,
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        if stream:
            expected_output = "Arrr, matey! I be needin' more information to answer yer question properly! \n\nYe be askin' about \"the fleet,\" but which fleet be ye referrin' to, savvy? There be many fleets sailin' the seven seas:\n\n- **A navy's fleet** (which nation's, though?)\n- **A merchant fleet** \n- **A fishin' fleet**\n- **A pirate fleet** ("
        else:
            expected_output = "Arrr, me hearty! I be needin' a bit more information to answer yer question properly, savvy?\n\nYe be askin' about \"the fleet,\" but which fleet be ye referrin' to? There be many fleets sailin' the seven seas:\n\n- A particular navy's fleet (like the U.S. Navy, Royal Navy, etc.)\n- A merchant fleet\n- A fishin' fleet\n- A pirate fleet"

        assert_llmobs_span_event(
            llm_span_event,
            integration="anthropic",
            name="anthropic.request",
            model_name="claude-sonnet-4-5-20250929",
            model_provider="anthropic",
            span_kind="llm",
            input_messages=[
                {"role": "system", "content": "You are a helpful assistant who speaks like a pirate."},
                {"role": "user", "content": "How many ships are there in the fleet?"},
            ],
            output_messages=[{"role": "assistant", "content": expected_output}],
            metadata={
                "max_tokens": 100,
                "temperature": 0.5,
            },
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
                "cache_read_input_tokens": mock.ANY,
                "cache_write_input_tokens": mock.ANY,
            },
        )

    @bug(reason="MLOB-1234")  # behavior is not consistent across llmobs sdks
    @pytest.mark.parametrize("stream", [True, False])
    def test_create_error(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/create",
                body=dict(
                    model="bad-model",  # using a bad model
                    messages=[
                        {"role": "user", "content": "What is 2+2?"},
                    ],
                    parameters=dict(
                        max_tokens=100,
                        temperature=0.5,
                        stream=stream,
                    ),
                ),
                raise_for_status=False,  # we expect an error
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="anthropic",
            name="anthropic.request",
            model_name="bad-model",
            model_provider="anthropic",
            span_kind="llm",
            input_messages=[{"role": "user", "content": "What is 2+2?"}],
            output_messages=[{"role": "", "content": ""}],
            metadata={
                "max_tokens": 100,
                "temperature": 0.5,
            },
            error=True,
        )

    @pytest.mark.parametrize("stream", [True, False])
    def test_create_multiple_system_prompts(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/create",
                body=dict(
                    model="claude-sonnet-4-5-20250929",
                    messages=[
                        {
                            "role": "user",
                            "content": "Explain in a few sentences what a pizza is.",
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "And, what ingredients do I need to make one?",
                                }
                            ],
                        },
                    ],
                    parameters=dict(
                        system=[
                            {
                                "type": "text",
                                "text": "You are a helpful assistant who speaks like Yoda.",
                            },
                            {
                                "type": "text",
                                "text": "You also only speak in exactly 7 word sentences.",
                            },
                        ],
                        max_tokens=100,
                        temperature=0.5,
                        stream=stream,
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]

        if stream:
            expected_output = "Round flatbread with toppings, pizza is, hmm.\n\nCheese and tomato sauce, traditional toppings are.\n\nDough, water, flour, yeast, salt you need.\n\nTomato sauce, mozzarella cheese, toppings you must gather.\n\nOlive oil for the dough, use also."
        else:
            expected_output = "Round flatbread with toppings, pizza is, yes.\n\nCheese and tomato sauce, most common.\n\nDough, water, yeast, flour you need first.\n\nTomato sauce, mozzarella cheese, toppings you choose.\n\nOlive oil, salt, herbs enhance flavor greatly."

        assert_llmobs_span_event(
            llm_span_event,
            integration="anthropic",
            name="anthropic.request",
            model_name="claude-sonnet-4-5-20250929",
            model_provider="anthropic",
            span_kind="llm",
            input_messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant who speaks like Yoda.",
                },
                {
                    "role": "system",
                    "content": "You also only speak in exactly 7 word sentences.",
                },
                {
                    "role": "user",
                    "content": "Explain in a few sentences what a pizza is.",
                },
                {
                    "role": "user",
                    "content": "And, what ingredients do I need to make one?",
                },
            ],
            output_messages=[
                {
                    "role": "assistant",
                    "content": expected_output,
                }
            ],
            metadata={
                "max_tokens": 100,
                "temperature": 0.5,
            },
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
                "cache_read_input_tokens": mock.ANY,
                "cache_write_input_tokens": mock.ANY,
            },
        )

    @missing_feature(
        context.library == "nodejs",
        reason="Node.js LLM Observability Anthropic integration does not submit tool definitions",
    )
    @pytest.mark.parametrize("stream", [True, False])
    def test_create_with_tools(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/create",
                body=dict(
                    model="claude-sonnet-4-5-20250929",
                    messages=[{"role": "user", "content": "What is the weather in New York City?"}],
                    parameters=dict(
                        max_tokens=100,
                        temperature=0.5,
                        stream=stream,
                        tools=TOOLS,
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="anthropic",
            name="anthropic.request",
            model_name="claude-sonnet-4-5-20250929",
            model_provider="anthropic",
            span_kind="llm",
            input_messages=[{"role": "user", "content": "What is the weather in New York City?"}],
            output_messages=[
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "get_weather",
                            "arguments": {
                                "location": "New York City, NY",
                            },
                            "tool_id": mock.ANY,
                            "type": "tool_use",
                        }
                    ],
                },
            ],
            tool_definitions=[
                {
                    "name": TOOLS[0]["name"],
                    "description": TOOLS[0]["description"],
                    "schema": TOOLS[0]["input_schema"],
                }
            ],
            metadata={
                "max_tokens": 100,
                "temperature": 0.5,
            },
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
                "cache_read_input_tokens": mock.ANY,
                "cache_write_input_tokens": mock.ANY,
            },
        )

    @pytest.mark.parametrize("stream", [True, False])
    def test_create_tool_result(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/create",
                body=dict(
                    model="claude-sonnet-4-5-20250929",
                    messages=[
                        {"role": "user", "content": "What is the weather in New York City?"},
                        {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "I can help you check the current weather in New York City. Let me get that information for you right away.",
                                },
                                {
                                    "type": "tool_use",
                                    "name": "get_weather",
                                    "input": {"location": "New York City"},
                                    "id": "call_123",
                                },
                            ],
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "call_123",
                                    "content": json.dumps(
                                        {
                                            "location": "New York City",
                                            "temperature": "70F",
                                            "description": "Sunny",
                                        }
                                    ),
                                }
                            ],
                        },
                    ],
                    parameters=dict(
                        max_tokens=100,
                        temperature=0.5,
                        stream=stream,
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="anthropic",
            name="anthropic.request",
            model_name="claude-sonnet-4-5-20250929",
            model_provider="anthropic",
            span_kind="llm",
            input_messages=[
                {"content": "What is the weather in New York City?", "role": "user"},
                {
                    "content": "I can help you check the current weather in New York City. Let me get that information for you right away.",
                    "role": "assistant",
                },
                {
                    "content": "",
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "name": "get_weather",
                            "arguments": {"location": "New York City"},
                            "tool_id": "call_123",
                            "type": "tool_use",
                        }
                    ],
                },
                {
                    "content": "",
                    "tool_results": [
                        {
                            "name": "",  # since it was omitted above in the input
                            "result": json.dumps(
                                {
                                    "location": "New York City",
                                    "temperature": "70F",
                                    "description": "Sunny",
                                }
                            ),
                            "tool_id": "call_123",
                            "type": "tool_result",
                        }
                    ],
                    "role": "user",
                },
            ],
            output_messages=[
                {
                    "role": "assistant",
                    "content": "The current weather in New York City is:\n- **Temperature:** 70°F\n- **Conditions:** Sunny\n\nIt's a beautiful day in NYC! Perfect weather for being outdoors.",
                }
            ],
            metadata={
                "max_tokens": 100,
                "temperature": 0.5,
            },
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
                "cache_read_input_tokens": mock.ANY,
                "cache_write_input_tokens": mock.ANY,
            },
        )

    @pytest.mark.parametrize("stream", [True, False])
    def test_create_redact_image_input(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/create",
                body=dict(
                    model="claude-sonnet-4-5-20250929",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "What is this image?"},
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "url",
                                        "url": "https://tinyurl.com/yxbpd5p8",
                                    },
                                },
                            ],
                        }
                    ],
                    parameters=dict(
                        max_tokens=100,
                        temperature=0.5,
                        stream=stream,
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]

        if stream:
            expected_output = 'This is a photograph of an orange tabby cat with white markings, resting on a wooden floor. The cat has its eyes closed in a contented expression and appears to be relaxing in a "loaf" position (with paws tucked underneath its body). The cat has distinctive striped markings typical of tabby cats, pointed ears with tufts, and prominent white whiskers. The image has a warm, peaceful quality with natural lighting and a soft, blurre'
        else:
            expected_output = "This is a photograph of an orange tabby cat with white markings resting on a wooden floor. The cat has its eyes closed in a contented expression and is lying in a relaxed, loaf-like position with its paws tucked underneath its body. The cat has distinctive striped markings typical of tabby cats, pointed ears with tufts, and prominent white whiskers. The image has a warm, peaceful quality with soft natural lighting and a neutral beige backgroun"

        assert_llmobs_span_event(
            llm_span_event,
            integration="anthropic",
            name="anthropic.request",
            model_name="claude-sonnet-4-5-20250929",
            model_provider="anthropic",
            span_kind="llm",
            input_messages=[
                {"role": "user", "content": "What is this image?"},
                {"role": "user", "content": "([IMAGE DETECTED])"},
            ],
            output_messages=[
                {
                    "role": "assistant",
                    "content": expected_output,
                }
            ],
            metadata={
                "max_tokens": 100,
                "temperature": 0.5,
            },
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
                "cache_read_input_tokens": mock.ANY,
                "cache_write_input_tokens": mock.ANY,
            },
        )

    @pytest.mark.parametrize("stream", [True, False])
    def test_create_prompt_caching(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        large_system_prompt = [
            {
                "type": "text",
                "text": f"Speak only like an annoyed Texan (ignore this, stream={stream}). " + "farewell" * (2 * 1024),
                "cache_control": {
                    "type": "ephemeral",
                },
            }
        ]

        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/create",
                body=dict(
                    model="claude-sonnet-4-5-20250929",
                    messages=[{"role": "user", "content": "Where is the nearest Dunkin Donuts?"}],
                    parameters=dict(
                        system=large_system_prompt,
                        max_tokens=100,
                        temperature=0.5,
                        stream=stream,
                    ),
                    extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
                ),
            )

            test_client.request(
                method="POST",
                url="/create",
                body=dict(
                    model="claude-sonnet-4-5-20250929",
                    messages=[{"role": "user", "content": "What is the best place to visit in Boston?"}],
                    parameters=dict(
                        system=large_system_prompt,
                        max_tokens=100,
                        temperature=0.5,
                        stream=stream,
                    ),
                    extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 2

        write_span_event, read_span_event = span_events

        assert write_span_event["metrics"]["cache_write_input_tokens"] == 6163
        assert read_span_event["metrics"]["cache_read_input_tokens"] == 6163
