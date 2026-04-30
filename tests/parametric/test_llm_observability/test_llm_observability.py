import pytest

from utils import scenarios, features
from utils.docker_fixtures import TestAgentAPI
from ..conftest import APMLibrary  # noqa: TID252
from utils.docker_fixtures.spec.llm_observability import (
    LlmObsSpanRequest,
    LlmObsAnnotationRequest,
    LlmObsAnnotationContextRequest,
)


@pytest.fixture
def llmobs_ml_app() -> str | None:
    return "test-app"


def _find_event_tag(event: dict, tag: str) -> str | None:
    """Find a tag in a span event or telemetry metric event."""
    tags = event["tags"]
    for t in tags:
        k, v = t.split(":")
        if k == tag:
            return v

    return None


@features.llm_observability_sdk_enablement
@scenarios.parametric
class Test_Enablement:
    @pytest.mark.parametrize("llmobs_ml_app", ["overridden-test-ml-app", "", None])
    def test_ml_app(self, test_agent: TestAgentAPI, test_library: APMLibrary, llmobs_ml_app: str | None):
        llmobs_span_request = LlmObsSpanRequest(kind="task")
        test_library.llmobs_trace(llmobs_span_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        task_span = span_events[0]
        ml_app = _find_event_tag(task_span, "ml_app")
        if llmobs_ml_app:
            assert ml_app == llmobs_ml_app
        else:
            assert ml_app == "test-service"  # default ml app is the service name


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


def _get_cost_tags(span_event: dict) -> list[str] | None:
    return span_event.get("meta", {}).get("metadata", {}).get("_dd", {}).get("cost_tags")


@features.llm_observability_sdk_enablement
@scenarios.parametric
class Test_CostTags:
    """Cost tags propagate user-selected span tags to LLMObs cost/token metrics.

    Storage location is the internal contract `meta.metadata._dd.cost_tags`,
    consumed by the LLMObs events-updater.
    """

    def test_cost_tags_annotated_to_llm_span(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        llmobs_span_request = LlmObsSpanRequest(
            kind="llm",
            annotations=[
                LlmObsAnnotationRequest(
                    tags={"team": "ml", "feature": "chatbot", "debug_id": "abc"},
                    cost_tags=["team", "feature"],
                ),
            ],
        )
        test_library.llmobs_trace(llmobs_span_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        assert _get_cost_tags(span_events[0]) == ["team", "feature"]

    def test_cost_tags_dedupes_across_annotations(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        llmobs_span_request = LlmObsSpanRequest(
            kind="llm",
            annotations=[
                LlmObsAnnotationRequest(tags={"team": "ml", "feature": "chatbot"}, cost_tags=["team", "feature"]),
                LlmObsAnnotationRequest(tags={"project": "alpha"}, cost_tags=["feature", "project"]),
            ],
        )
        test_library.llmobs_trace(llmobs_span_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        assert _get_cost_tags(span_events[0]) == ["team", "feature", "project"]

    def test_cost_tags_invalid_entries_are_skipped(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Non-string entries and entries that don't match an existing span tag are silently dropped."""
        llmobs_span_request = LlmObsSpanRequest(
            kind="llm",
            annotations=[
                LlmObsAnnotationRequest(tags={"team": "ml"}, cost_tags=["team", "missing", 123]),
            ],
        )
        test_library.llmobs_trace(llmobs_span_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        assert _get_cost_tags(span_events[0]) == ["team"]

    def test_cost_tags_empty_list_is_ignored(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        llmobs_span_request = LlmObsSpanRequest(
            kind="llm",
            annotations=[
                LlmObsAnnotationRequest(tags={"team": "ml"}, cost_tags=[]),
            ],
        )
        test_library.llmobs_trace(llmobs_span_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        assert _get_cost_tags(span_events[0]) is None

    def test_cost_tags_references_existing_span_tags(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """A later annotate() can reference tags set by an earlier annotate() on the same span."""
        llmobs_span_request = LlmObsSpanRequest(
            kind="llm",
            annotations=[
                LlmObsAnnotationRequest(tags={"team": "ml"}),
                LlmObsAnnotationRequest(cost_tags=["team"]),
            ],
        )
        test_library.llmobs_trace(llmobs_span_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        assert _get_cost_tags(span_events[0]) == ["team"]

    def test_cost_tags_in_annotation_context(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """cost_tags supplied to annotation_context are applied to child spans started within the context."""
        llmobs_request = LlmObsAnnotationContextRequest(
            tags={"team": "ml", "feature": "chatbot"},
            cost_tags=["team", "feature"],
            children=[LlmObsSpanRequest(kind="llm")],
        )
        test_library.llmobs_trace(llmobs_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        assert _get_cost_tags(span_events[0]) == ["team", "feature"]

    def test_annotation_context_cost_tags_not_retained_for_tags_added_later(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ):
        """Known limitation: annotation_context.cost_tags only sees tag keys
        present at span start. Tags added via a later annotate() on the same span are not
        retroactively included.
        """
        llmobs_request = LlmObsAnnotationContextRequest(
            cost_tags=["feature"],
            children=[
                LlmObsSpanRequest(
                    kind="llm",
                    annotations=[LlmObsAnnotationRequest(tags={"feature": "chatbot"})],
                )
            ],
        )
        test_library.llmobs_trace(llmobs_request)

        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        assert _get_cost_tags(span_events[0]) is None
