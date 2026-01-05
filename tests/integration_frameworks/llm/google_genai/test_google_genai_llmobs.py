import json
from tests.integration_frameworks.llm.utils import assert_llmobs_span_event
from utils import features, missing_feature, scenarios, bug, context
from utils.docker_fixtures import FrameworkTestClientApi, TestAgentAPI

import pytest
from unittest import mock
from typing import Any

from .utils import BaseGoogleGenaiTest


@pytest.fixture
def library_env() -> dict[str, str]:
    return {
        "DD_LLMOBS_ENABLED": "true",
        "DD_LLMOBS_ML_APP": "test-app",
    }


GET_WEATHER_TOOL = {
    "name": "get_weather",
    "description": "Get the weather in a given location",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The location to get the weather for",
            },
        },
    },
}

GET_WEATHER_TOOL_DEFINITION_SCHEMA = {
    "name": GET_WEATHER_TOOL["name"],
    "description": GET_WEATHER_TOOL["description"],
    "schema": GET_WEATHER_TOOL["parameters"],
}


def format_expected_metadata(**metadata: Any) -> dict[str, Any]:  # noqa: ANN401
    expected_metadata = {
        "temperature": None,
        "top_p": None,
        "top_k": None,
        "candidate_count": None,
        "max_output_tokens": None,
        "stop_sequences": None,
        "response_logprobs": None,
        "logprobs": None,
        "presence_penalty": None,
        "frequency_penalty": None,
        "seed": None,
        "response_mime_type": None,
        "safety_settings": None,
        "automatic_function_calling": None,
    }

    expected_metadata.update({key: value for key, value in metadata.items() if value is not None})

    return expected_metadata


@features.llm_observability_google_genai_generate_content
@scenarios.integration_frameworks
class TestGoogleGenAiGenerateContent(BaseGoogleGenaiTest):
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

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]

        if stream:
            expected_output = "This is a classic joke! Here are a few possible answers, ranging from the traditional to the more absurd:\n\n*   **The Classic:** To get to the other side.\n*   **The Logical:** Because there was a chicken crossing signal"
        else:
            expected_output = "This is a classic joke! Here are a few possible answers, ranging from the traditional to the more absurd:\n\n*   **The Classic:** To get to the other side.\n*   **The Logical:** Because there was a road there."

        assert_llmobs_span_event(
            llm_span_event,
            integration="google_genai",
            name="google_genai.request",
            span_kind="llm",
            model_name="gemini-2.0-flash",
            model_provider="google",
            input_messages=[{"role": "user", "content": "Why did the chicken cross the road?"}],
            output_messages=[{"role": "assistant", "content": expected_output}],
            metadata=format_expected_metadata(temperature=0.1, max_output_tokens=50),
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
            },
        )

    @pytest.mark.parametrize("stream", [True, False])
    def test_generate_content_multiple_strings_input(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/generate_content",
                body=dict(
                    model="gemini-2.0-flash",
                    contents=["Why did the chicken cross the road?", "What is 2 + 2?"],
                    config=dict(
                        temperature=0.1,
                        max_output_tokens=50,
                        stream=stream,
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="google_genai",
            name="google_genai.request",
            span_kind="llm",
            model_name="gemini-2.0-flash",
            model_provider="google",
            input_messages=[
                {"role": "user", "content": "Why did the chicken cross the road?"},
                {"role": "user", "content": "What is 2 + 2?"},
            ],
            output_messages=[
                {
                    "role": "assistant",
                    "content": "Okay, here are the answers to your questions:\n\n*   **Why did the chicken cross the road?** To get to the other side.\n\n*   **What is 2 + 2?** 4",
                }
            ],
            metadata=format_expected_metadata(temperature=0.1, max_output_tokens=50),
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
            },
        )

    @pytest.mark.parametrize("stream", [True, False])
    def test_generate_content_parts_input(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/generate_content",
                body=dict(
                    model="gemini-2.0-flash",
                    contents=[
                        {"text": "Why did the chicken cross the road?"},
                        {"text": "What is 2 + 2?"},
                    ],
                    config=dict(
                        temperature=0.1,
                        max_output_tokens=50,
                        stream=stream,
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="google_genai",
            name="google_genai.request",
            span_kind="llm",
            model_name="gemini-2.0-flash",
            model_provider="google",
            input_messages=[
                {"role": "user", "content": "Why did the chicken cross the road?"},
                {"role": "user", "content": "What is 2 + 2?"},
            ],
            output_messages=[
                {
                    "role": "assistant",
                    "content": "Okay, here are the answers to your questions:\n\n*   **Why did the chicken cross the road?** To get to the other side.\n\n*   **What is 2 + 2?** 4",
                }
            ],
            metadata=format_expected_metadata(temperature=0.1, max_output_tokens=50),
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
            },
        )

    @pytest.mark.parametrize("stream", [True, False])
    def test_generate_content_content_block_input(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/generate_content",
                body=dict(
                    model="gemini-2.0-flash",
                    contents=[
                        {
                            "parts": [{"text": "Why did the chicken cross the road?"}],
                            "role": "user",
                        },
                    ],
                    config=dict(
                        temperature=0.1,
                        max_output_tokens=50,
                        stream=stream,
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        if stream:
            expected_output = "This is a classic joke! Here are a few possible answers, ranging from the traditional to the more absurd:\n\n*   **The Classic:** To get to the other side.\n*   **The Logical:** Because there was a chicken on the"
        else:
            expected_output = "This is a classic joke! Here are a few possible answers, ranging from the traditional to the more absurd:\n\n*   **The Classic:** To get to the other side.\n*   **The Logical:** Because there was a chicken crossing signal"

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="google_genai",
            name="google_genai.request",
            span_kind="llm",
            model_name="gemini-2.0-flash",
            model_provider="google",
            input_messages=[{"role": "user", "content": "Why did the chicken cross the road?"}],
            output_messages=[{"role": "assistant", "content": expected_output}],
            metadata=format_expected_metadata(temperature=0.1, max_output_tokens=50),
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
            },
        )


@features.llm_observability_google_genai_generate_content_reasoning
@scenarios.integration_frameworks
class TestGoogleGenAiGenerateContentReasoning(BaseGoogleGenaiTest):
    # python does not have reasoning output messages for streamed responses
    @bug(context.library == "python", reason="MLOB-5071")
    @pytest.mark.parametrize("stream", [True, False])
    def test_generate_content_reasoning_output(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/generate_content",
                body=dict(
                    model="gemini-2.5-pro",
                    contents="If x + 9 = 10, what is the value of x?",
                    config=dict(
                        thinking_config=dict(
                            thinking_budget=1024,
                            include_thoughts=True,
                        ),
                        stream=stream,
                        temperature=0.1,
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        # TODO: python will need different assertions for output messages (cassette is different)

        if stream:
            reasoning_output = "**Focusing on Simplification**\n\nCurrently, I'm focusing on the essential simplification needed for the user's equation, `x + 9 = 10`. I've quickly identified it as a straightforward linear equation requiring only one step to isolate 'x'. My next step is to formulate the required operations explicitly.\n\n\n**Decomposing the Solution**\n\nI've carefully decomposed the solution process. First, I pinpointed the user's objective: determine 'x'. Then, I analyzed the linear equation `x + 9 = 10`. Next, I formulated the required subtraction. I then carefully outlined the steps, ensuring the equation remains balanced by applying the subtraction to both sides. Finally, I verified the solution by substituting it back into the original equation and confirming the equality holds, leading to the correct answer.\n\n\n**Developing the Response**\n\nI've just structured the final response, starting with the answer for clarity. The explanation now includes isolating the variable and subtraction from both sides. I'll include a verification step to ensure confidence, and plan to use clear, helpful language. I'm focusing on simplicity and directness in my phrasing.\n\n\n"
            assistant_output = "To find the value of x, you need to get x by itself on one side of the equation.\n\nHere's the equation:\nx + 9 = 10\n\nTo isolate x, subtract 9 from both sides of the equation:\nx + 9 - 9 = 10 - 9\nx = 1\n\nSo, the value of **x is 1**."
        else:
            reasoning_output = "**Walking Through the Solution: Finding the Value of x**\n\nOkay, so the user wants to solve for 'x' in the equation x + 9 = 10.  It's a straightforward linear equation – a single step to isolate the variable.  My mind immediately jumps to the process.  The equation's x + 9 = 10.  The goal is crystal clear: get 'x' all alone on one side.\n\nThe '+ 9' is the obstacle.  I know the principle: I have to do the *opposite* of addition to get rid of it. Subtraction. And, crucially, whatever I do to one side of the equation, I must do to the *other* to keep things balanced.\n\nSo, I subtract 9 from both sides: (x + 9) - 9 = 10 - 9. That means on the left side, the '+9' and '-9' cancel each other out, leaving just 'x'.  On the right side, 10 minus 9 is 1.\n\nThe simplified equation then becomes x = 1.\n\nNow, to present this clearly and accessibly to the user. I'd begin with the answer: x = 1.  Then I'd break down the steps:\n\n1.  Start with the given equation: x + 9 = 10\n2.  The goal: Isolate x on one side of the equation.\n3.  Action: Subtract 9 from both sides.\n4.  Calculation:\n    *   x + 9 - 9 = 10 - 9\n    *   x = 1\n\nThen to conclude, the final answer: x = 1.\n\nIt's clear, correct, and follows basic algebraic principles, which is perfect.\n"  # noqa: RUF001
            assistant_output = "To find the value of x, you need to get x by itself on one side of the equation.\n\nGiven the equation:\nx + 9 = 10\n\nSubtract 9 from both sides of the equation:\nx + 9 - 9 = 10 - 9\n\nThis simplifies to:\nx = 1\n\nSo, the value of **x is 1**."

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="google_genai",
            name="google_genai.request",
            span_kind="llm",
            model_name="gemini-2.5-pro",
            model_provider="google",
            input_messages=[{"role": "user", "content": "If x + 9 = 10, what is the value of x?"}],
            output_messages=[
                {
                    "role": "reasoning",
                    "content": reasoning_output,
                },
                {
                    "role": "assistant",
                    "content": assistant_output,
                },
            ],
            metadata=format_expected_metadata(temperature=0.1),
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
            },
        )

    @pytest.mark.parametrize("stream", [True, False])
    def test_generate_content_reasoning_input(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        input_messages = [
            {
                "parts": [{"text": "If x + 9 = 10, what is the value of x?"}],
                "role": "user",
            },
            {
                "parts": [{"text": "Since 1 + 9 = 10, the value of x is 1.", "thought": True}],
                "role": "model",
            },
            {"parts": [{"text": "The value of x is 1."}], "role": "model"},
            {"parts": [{"text": "What is that number plus 3?"}], "role": "user"},
        ]

        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/generate_content",
                body=dict(
                    model="gemini-2.0-flash",
                    contents=input_messages,
                    config=dict(
                        stream=stream,
                        temperature=0.1,
                        max_output_tokens=50,
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="google_genai",
            name="google_genai.request",
            span_kind="llm",
            model_name="gemini-2.0-flash",
            model_provider="google",
            input_messages=[
                {"role": "user", "content": "If x + 9 = 10, what is the value of x?"},
                {
                    "role": "reasoning",
                    "content": "Since 1 + 9 = 10, the value of x is 1.",
                },
                {"role": "assistant", "content": "The value of x is 1."},
                {"role": "user", "content": "What is that number plus 3?"},
            ],
            output_messages=[
                {
                    "role": "assistant",
                    "content": "The number is 1. Adding 3 to it gives 1 + 3 = 4.\n\nSo the answer is 4.\n",
                },
            ],
            metadata=format_expected_metadata(temperature=0.1, max_output_tokens=50),
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
            },
        )


@features.llm_observability_google_genai_generate_content_with_tools
@scenarios.integration_frameworks
class TestGoogleGenAiGenerateContentWithTools(BaseGoogleGenaiTest):
    # tool definitions do not seem to be formatted correctly
    @bug(context.library == "python", reason="MLOB-5071")
    @missing_feature(
        context.library == "nodejs",
        reason="Node.js LLM Observability Google GenAI integration does not submit tool definitions",
    )
    @pytest.mark.parametrize("stream", [True, False])
    def test_generate_content_with_tools(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/generate_content",
                body=dict(
                    model="gemini-2.0-flash",
                    contents="What is the weather in Tokyo?",
                    config=dict(
                        max_output_tokens=50, stream=stream, tools=[{"function_declarations": [GET_WEATHER_TOOL]}]
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="google_genai",
            name="google_genai.request",
            span_kind="llm",
            model_name="gemini-2.0-flash",
            model_provider="google",
            input_messages=[{"role": "user", "content": "What is the weather in Tokyo?"}],
            output_messages=[
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "name": "get_weather",
                            "arguments": {"location": "Tokyo"},
                            "tool_id": mock.ANY,
                            "type": "function_call",
                        }
                    ],
                },
            ],
            tool_definitions=[GET_WEATHER_TOOL_DEFINITION_SCHEMA],
            metadata=format_expected_metadata(max_output_tokens=50),
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
            },
        )

    @pytest.mark.parametrize("stream", [True, False])
    def test_generate_content_with_tool_responses(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        input_messages = [
            {"parts": [{"text": "What is the weather in Tokyo?"}], "role": "user"},
            {
                "parts": [
                    {
                        "function_call": {
                            "name": "get_weather",
                            "args": {"location": "Tokyo"},
                            "id": "abc123",
                        }
                    }
                ],
                "role": "model",
            },
            {
                "parts": [
                    {
                        "function_response": {
                            "name": "get_weather",
                            "response": {"weather": "sunny", "temperature": "78°F"},
                            "id": "abc123",
                        }
                    }
                ],
                "role": "user",
            },
        ]

        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/generate_content",
                body=dict(
                    model="gemini-2.0-flash",
                    contents=input_messages,
                    config=dict(
                        max_output_tokens=50,
                        temperature=0.1,
                        stream=stream,
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="google_genai",
            name="google_genai.request",
            span_kind="llm",
            model_name="gemini-2.0-flash",
            model_provider="google",
            input_messages=[
                {"role": "user", "content": "What is the weather in Tokyo?"},
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "name": "get_weather",
                            "arguments": {"location": "Tokyo"},
                            "tool_id": "abc123",
                            "type": "function_call",
                        }
                    ],
                },
                {
                    "role": "user",
                    "tool_results": [
                        {
                            "name": "get_weather",
                            "result": mock.ANY,
                            "tool_id": "abc123",
                            "type": "function_response",
                        }
                    ],
                },
            ],
            output_messages=[
                {"role": "assistant", "content": "The weather in Tokyo is sunny with a temperature of 78°F.\n"}
            ],
            metadata=format_expected_metadata(max_output_tokens=50, temperature=0.1),
            metrics={
                "input_tokens": mock.ANY,
                "output_tokens": mock.ANY,
                "total_tokens": mock.ANY,
            },
        )

        # assert tool result formatting separately
        tool_result = json.loads(llm_span_event["meta"]["input"]["messages"][2]["tool_results"][0]["result"])
        assert tool_result["weather"] == "sunny"
        assert (
            "78" in tool_result["temperature"]
        )  # there are some subtle character formatting differences for the degree symbol in different client libraries

    # Node.js does not have 4 output messages for non-streamed responses
    @bug(context.library == "nodejs", reason="MLOB-5070")
    @pytest.mark.parametrize("stream", [True, False])
    def test_generate_content_executable_code(
        self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi, *, stream: bool
    ):
        with test_agent.vcr_context(stream=stream):
            test_client.request(
                method="POST",
                url="/generate_content",
                body=dict(
                    model="gemini-2.5-flash",
                    contents="What is the sum of the first 50 prime numbers? Generate and run code for the calculation, and make sure you get all 50.",
                    config=dict(
                        tools=[{"code_execution": {}}],
                        stream=stream,
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        if stream:
            assert len(llm_span_event["meta"]["output"]["messages"]) == 3
            expected_output_messages = [
                {"role": "assistant", "content": mock.ANY},
                {
                    "role": "assistant",
                    "content": {"language": mock.ANY, "code": mock.ANY},
                },
                {
                    "role": "assistant",
                    "content": {"outcome": mock.ANY, "output": mock.ANY},
                },
            ]
        else:
            #  non-streamed responses return the outcome of the third block as the content of the last block for some reason
            assert len(llm_span_event["meta"]["output"]["messages"]) == 4
            expected_output_messages = [
                {"role": "assistant", "content": mock.ANY},
                {
                    "role": "assistant",
                    "content": {"language": mock.ANY, "code": mock.ANY},
                },
                {
                    "role": "assistant",
                    "content": {"outcome": mock.ANY, "output": mock.ANY},
                },
                {"role": "assistant", "content": mock.ANY},
            ]

        actual_output_messages = llm_span_event["meta"]["output"]["messages"]

        #  Order is not guaranteed for output messages from the Gemini API, so we do a check over each set of actual & expected messages
        for expected_message in expected_output_messages:
            found = False
            for actual_message in actual_output_messages:
                try:
                    assert actual_message["role"] == expected_message["role"]
                    try:
                        assert json.loads(actual_message["content"]) == expected_message["content"]
                    except json.JSONDecodeError:
                        assert actual_message["content"] == expected_message["content"]
                    found = True
                    break
                except AssertionError:
                    continue
            assert found, f"Did not find expected message {expected_message} in {actual_output_messages}"


@features.llm_observability_google_genai_embed_content
@scenarios.integration_frameworks
class TestGoogleGenAiEmbedContent(BaseGoogleGenaiTest):
    def test_embed_content(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        with test_agent.vcr_context():
            test_client.request(
                method="POST",
                url="/embed_content",
                body=dict(
                    model="text-embedding-004",
                    contents="Why did the chicken cross the road?",
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="google_genai",
            name="google_genai.request",
            span_kind="embedding",
            model_name="text-embedding-004",
            model_provider="google",
            input_documents=[{"text": "Why did the chicken cross the road?"}],
            output_value="[1 embedding(s) returned with size 768]",
            metadata={},
            metrics={},  # metrics are not returned directly with google genai embedding models
        )

    def test_embed_content_multiple_strings_input(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        with test_agent.vcr_context():
            test_client.request(
                method="POST",
                url="/embed_content",
                body=dict(
                    model="text-embedding-004",
                    contents=["Why did the chicken cross the road?", "What is 2 + 2?"],
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="google_genai",
            name="google_genai.request",
            span_kind="embedding",
            model_name="text-embedding-004",
            model_provider="google",
            input_documents=[{"text": "Why did the chicken cross the road?"}, {"text": "What is 2 + 2?"}],
            output_value="[2 embedding(s) returned with size 768]",
            metadata={},
            metrics={},
        )

    def test_embed_content_parts_input(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        with test_agent.vcr_context():
            test_client.request(
                method="POST",
                url="/embed_content",
                body=dict(
                    model="text-embedding-004",
                    contents=[{"text": "Why did the chicken cross the road?"}, {"text": "What is 2 + 2?"}],
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="google_genai",
            name="google_genai.request",
            span_kind="embedding",
            model_name="text-embedding-004",
            model_provider="google",
            input_documents=[{"text": "Why did the chicken cross the road?"}, {"text": "What is 2 + 2?"}],
            output_value="[2 embedding(s) returned with size 768]",
            metadata={},
            metrics={},
        )

    def test_embed_content_content_block_input(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        with test_agent.vcr_context():
            test_client.request(
                method="POST",
                url="/embed_content",
                body=dict(
                    model="text-embedding-004",
                    contents=[
                        {
                            "parts": [
                                {"text": "Why did the chicken cross the road?"},
                                {"text": "What is 2 + 2?"},
                            ],
                            "role": "user",
                        },
                    ],
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="google_genai",
            name="google_genai.request",
            span_kind="embedding",
            model_name="text-embedding-004",
            model_provider="google",
            input_documents=[{"text": "Why did the chicken cross the road?"}, {"text": "What is 2 + 2?"}],
            output_value="[1 embedding(s) returned with size 768]",  # the inputs are combined into a single input for google genai purposes
            metadata={},
            metrics={},
        )

    def test_embed_content_with_metadata(self, test_agent: TestAgentAPI, test_client: FrameworkTestClientApi):
        with test_agent.vcr_context():
            test_client.request(
                method="POST",
                url="/embed_content",
                body=dict(
                    model="text-embedding-004",
                    contents="Why did the chicken cross the road?",
                    config=dict(
                        output_dimensionality=10,
                    ),
                ),
            )

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        llm_span_event = span_events[0]
        assert_llmobs_span_event(
            llm_span_event,
            integration="google_genai",
            name="google_genai.request",
            span_kind="embedding",
            model_name="text-embedding-004",
            model_provider="google",
            input_documents=[{"text": "Why did the chicken cross the road?"}],
            output_value="[1 embedding(s) returned with size 10]",
            metadata={
                "auto_truncate": None,
                "mime_type": None,
                "output_dimensionality": 10,
                "task_type": None,
                "title": None,
            },
            metrics={},
        )
