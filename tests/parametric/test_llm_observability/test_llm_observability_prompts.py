from utils.docker_fixtures import TestAgentAPI
from ..conftest import APMLibrary  # noqa: TID252
from utils.docker_fixtures.spec.llm_observability import (
    LlmObsSpanRequest,
    LlmObsAnnotationRequest,
    LlmObsAnnotationContextRequest,
)

from utils import features, scenarios


@features.llm_observability_prompts
@scenarios.parametric
class Test_Prompts:
    def test_prompt_annotation(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        llmobs_span_request = LlmObsSpanRequest(
            kind="llm",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data="This is a test query",
                    prompt={
                        "chat_template": [{"role": "user", "content": "This is a {{query}}"}],
                        "version": "1",
                        "variables": {"query": "test query"},
                    },
                )
            ],
        )

        test_library.llmobs_trace(llmobs_span_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        span_event = span_events[0]
        prompt = span_event["meta"]["input"]["prompt"]
        assert prompt["chat_template"] == [{"role": "user", "content": "This is a {{query}}"}]
        assert prompt["version"] == "1"
        assert prompt["variables"] == {"query": "test query"}

    def test_prompt_annotation_with_non_llm_span_does_not_annotate(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ):
        llmobs_span_request = LlmObsSpanRequest(
            kind="task",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data="This is a test query",
                    prompt={
                        "chat_template": [{"role": "user", "content": "This is a test query"}],
                        "version": "1",
                        "variables": {"query": "test query"},
                    },
                )
            ],
        )

        test_library.llmobs_trace(llmobs_span_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        span_event = span_events[0]
        assert "prompt" not in span_event["meta"]["input"]

    def test_prompt_annotation_with_string_template(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        llmobs_span_request = LlmObsSpanRequest(
            kind="llm",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data="This is a test query",
                    prompt={
                        "template": "This is a {{query}}",
                        "version": "1",
                        "variables": {"query": "test query"},
                    },
                )
            ],
        )

        test_library.llmobs_trace(llmobs_span_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        span_event = span_events[0]
        prompt = span_event["meta"]["input"]["prompt"]

        assert prompt["template"] == "This is a {{query}}"
        assert prompt["version"] == "1"
        assert prompt["variables"] == {"query": "test query"}

    def test_prompt_annotation_supports_tags(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        llmobs_span_request = LlmObsSpanRequest(
            kind="llm",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data="This is a test query",
                    prompt={
                        "chat_template": [{"role": "user", "content": "This is a test query"}],
                        "version": "1",
                        "variables": {"query": "test query"},
                        "tags": {"foo": "bar"},
                    },
                )
            ],
        )

        test_library.llmobs_trace(llmobs_span_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        span_event = span_events[0]
        prompt = span_event["meta"]["input"]["prompt"]
        assert prompt["tags"] == {"foo": "bar"}

    def test_prompt_annotation_supports_hallucinations(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        template = (
            "Please write a poem about {{query}}. Base it off of the following excerpts from {{author}}: {{excerpts}}"
        )
        llmobs_span_request = LlmObsSpanRequest(
            kind="llm",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data="Please write a poem about flowers. Base it off of the following excerpts from Test Author: Test Excerpts",
                    prompt={
                        "chat_template": [{"role": "user", "content": template}],
                        "version": "1",
                        "variables": {"query": "flowers", "author": "Test Author", "excerpts": "Test Excerpts"},
                        "rag_query_variables": ["query"],
                        "rag_context_variables": ["author", "excerpts"],
                    },
                )
            ],
        )

        test_library.llmobs_trace(llmobs_span_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        span_event = span_events[0]
        prompt = span_event["meta"]["input"]["prompt"]
        assert prompt["chat_template"] == [{"role": "user", "content": template}]
        assert prompt["version"] == "1"
        assert prompt["variables"] == {"query": "flowers", "author": "Test Author", "excerpts": "Test Excerpts"}
        assert prompt["_dd_query_variable_keys"] == ["query"]
        assert prompt["_dd_context_variable_keys"] == ["author", "excerpts"]

    def test_prompt_annotation_in_annotation_context(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        llmobs_request = LlmObsAnnotationContextRequest(
            prompt={
                "chat_template": [{"role": "user", "content": "This is a test query"}],
                "version": "1",
                "variables": {"query": "test query"},
            },
            children=[
                LlmObsSpanRequest(
                    kind="llm",
                    annotations=[
                        LlmObsAnnotationRequest(
                            input_data="This is a test query",
                        )
                    ],
                )
            ],
        )

        test_library.llmobs_trace(llmobs_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        span_event = span_events[0]
        prompt = span_event["meta"]["input"]["prompt"]

        assert prompt["chat_template"] == [{"role": "user", "content": "This is a test query"}]
        assert prompt["version"] == "1"
        assert prompt["variables"] == {"query": "test query"}

    def test_prompt_annotation_default_id(
        self, test_agent: TestAgentAPI, test_library: APMLibrary, llmobs_ml_app: str | None
    ):
        default_prompt_id = f"{llmobs_ml_app}_unnamed-prompt"

        llmobs_span_request = LlmObsSpanRequest(
            kind="llm",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data="This is a test query",
                    prompt={
                        "chat_template": [{"role": "user", "content": "This is a test query"}],
                        "variables": {"query": "test query"},
                    },
                )
            ],
        )

        test_library.llmobs_trace(llmobs_span_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        span_event = span_events[0]
        prompt = span_event["meta"]["input"]["prompt"]
        assert prompt["id"] == default_prompt_id

    def test_prompt_annotation_updates_existing_prompt(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        llmobs_span_request = LlmObsSpanRequest(
            kind="llm",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data="This is a test query",
                    prompt={
                        "chat_template": [{"role": "user", "content": "This is a test query"}],
                        "version": "1",
                        "variables": {"query": "test query"},
                    },
                ),
                LlmObsAnnotationRequest(
                    prompt={"tags": {"foo": "bar"}},  # simulating tags being set at a later time
                ),
            ],
        )

        test_library.llmobs_trace(llmobs_span_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        span_event = span_events[0]
        prompt = span_event["meta"]["input"]["prompt"]
        assert prompt["chat_template"] == [{"role": "user", "content": "This is a test query"}]
        assert prompt["version"] == "1"
        assert prompt["variables"] == {"query": "test query"}
        assert prompt["tags"] == {"foo": "bar"}
