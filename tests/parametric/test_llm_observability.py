import os
from utils import scenarios, features
from utils.docker_fixtures import TestAgentAPI
from .conftest import APMLibrary
from utils.docker_fixtures.spec.llm_observability import (
    LlmObsSpanRequest,
    LlmObsAnnotationRequest,
    LlmObsAnnotationContextRequest,
)
import pytest


@pytest.fixture
def llmobs_enabled() -> bool:
    return True


@pytest.fixture
def llmobs_ml_app() -> str | None:
    return "test-app"


@pytest.fixture
def dd_service() -> str:
    return "test-service"


@pytest.fixture
def dd_llmobs_agentless_enabled() -> bool | None:
    return False


@pytest.fixture
def dd_llmobs_override_origin() -> str | None:
    return None


@pytest.fixture
def library_env(
    llmobs_ml_app: str | None,
    dd_llmobs_override_origin: str | None,
    dd_service: str,
    *,
    llmobs_enabled: bool | None,
    dd_llmobs_agentless_enabled: bool | None,
) -> dict[str, object]:
    env: dict[str, object] = {
        "DD_SERVICE": dd_service,
        # TODO: below need to be more robust, follow other similar practices for api/app keys
        "DD_API_KEY": os.environ.get("DD_API_KEY"),
        "DD_APP_KEY": os.environ.get("DD_APPLICATION_KEY"),
    }

    if llmobs_enabled is not None:
        env["DD_LLMOBS_ENABLED"] = llmobs_enabled

    if llmobs_ml_app is not None:
        env["DD_LLMOBS_ML_APP"] = llmobs_ml_app

    if dd_llmobs_agentless_enabled is not None:
        env["DD_LLMOBS_AGENTLESS_ENABLED"] = dd_llmobs_agentless_enabled

    if dd_llmobs_override_origin is not None:
        env["DD_LLMOBS_OVERRIDE_ORIGIN"] = dd_llmobs_override_origin
        env["_DD_LLMOBS_OVERRIDE_ORIGIN"] = dd_llmobs_override_origin

    return env


@pytest.fixture
def agent_env() -> dict[str, object]:
    return {"VCR_IGNORE_HEADERS": "content-security-policy"}


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


@scenarios.parametric
class Test_Datasets:
    @pytest.fixture
    def dd_llmobs_override_origin(self, test_agent: TestAgentAPI) -> str:
        return f"http://{test_agent.container_name}:{test_agent.container_port}/vcr/datadog"

    def test_dataset_create(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with test_agent.vcr_context():
            ds = test_library.llmobs_dataset_create(  # noqa: F841
                dataset_name="test-dataset",
                records=[],
            )


@scenarios.parametric
class Test_Experiments:
    @pytest.fixture
    def dd_llmobs_override_origin(self, test_agent: TestAgentAPI) -> str:
        return f"http://{test_agent.container_name}:{test_agent.container_port}/vcr/datadog"

    def test_experiment_create(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with test_agent.vcr_context():
            ds = test_library.llmobs_dataset_create(
                dataset_name="capitals-of-the-world-system-tests",
                project_name="capitals-project",
                description="Questions about world capitals",
                records=[
                    {
                        "input_data": {"question": "What is the capital of China?"},  # required, JSON or string
                        "expected_output": "Beijing",  # optional, JSON or string
                        "metadata": {"difficulty": "easy"},  # optional, JSON
                    },
                    {
                        "input_data": {"question": "Which city serves as the capital of South Africa?"},
                        "expected_output": "Pretoria",
                        "metadata": {"difficulty": "medium"},
                    },
                ],
            )

            assert ds is not None, "Dataset creation failed"
            assert isinstance(ds, dict), "Dataset is not a dictionary"

            experiments_result = test_library.llmobs_experiment_create(  # noqa: F841
                experiment_name="capital-cities-test-system-tests",
                task="task",  # maps to a "task" function
                dataset=ds,
                evaluators=["exact_match", "overlap", "fake_llm_as_a_judge"],
                description="Testing capital cities knowledge",
                config={"model": "gpt-4", "version": "1.0"},
                jobs=4,
            )

            assert "rows" in experiments_result
