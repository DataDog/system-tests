from utils.docker_fixtures import TestAgentAPI
from ..conftest import APMLibrary  # noqa: TID252
from utils.docker_fixtures.spec.llm_observability import (
    LlmObsSpanRequest,
    ApmSpanRequest,
)

from .utils import find_event_tag
from utils import scenarios
import pytest

SPAN_KINDS = [
    {"kind": "task", "requires_model": False},
    {"kind": "llm", "requires_model": True},
    {"kind": "workflow", "requires_model": False},
    {"kind": "agent", "requires_model": False},
    {"kind": "retrieval", "requires_model": False},
    {"kind": "embedding", "requires_model": True},
    {"kind": "tool", "requires_model": False},
]


# TODO: add feature
@scenarios.parametric
class Test_Tracing:
    @pytest.mark.parametrize(
        "kind_info",
        SPAN_KINDS,
        ids=lambda span_kind_info: f"test_{span_kind_info['kind']}_span",
    )
    def test_trace_spans(self, test_agent: TestAgentAPI, test_library: APMLibrary, kind_info: dict):
        kind = kind_info["kind"]
        requires_model = kind_info["requires_model"]

        llmobs_span = LlmObsSpanRequest(
            kind=kind,
            name=f"test_{kind}",
            session_id="test_id",
            ml_app="test_app",
        )

        if requires_model:
            llmobs_span.model_name = "test_model"
            llmobs_span.model_provider = "test_provider"

        test_library.llmobs_trace(llmobs_span)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1

        span_event = span_events[0]
        if requires_model:
            assert span_event["meta"]["model_name"] == "test_model"
            assert span_event["meta"]["model_provider"] == "test_provider"

    def test_sets_parentage_simple(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="workflow",
            name="test-workflow",
            children=[
                LlmObsSpanRequest(
                    kind="task",
                    name="test-task",
                )
            ],
        )

        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 2

        workflow_span_event, task_span_event = span_events
        assert workflow_span_event["name"] == "test-workflow"
        assert task_span_event["name"] == "test-task"
        assert workflow_span_event["parent_id"] == "undefined"
        assert task_span_event["parent_id"] == workflow_span_event["span_id"]

    def test_sets_parentage_apm_spans(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="workflow",
            name="test-workflow",
            children=[
                ApmSpanRequest(
                    name="apm-span",
                    children=[
                        LlmObsSpanRequest(
                            kind="task",
                            name="test-task",
                        )
                    ],
                )
            ],
        )

        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 2

        workflow_span_event, task_span_event = span_events

        assert workflow_span_event["name"] == "test-workflow"
        assert task_span_event["name"] == "test-task"
        assert workflow_span_event["parent_id"] == "undefined"
        assert task_span_event["parent_id"] == workflow_span_event["span_id"]

    def test_sets_parentage_apm_root_span(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = ApmSpanRequest(
            name="apm-root-span",
            children=[
                LlmObsSpanRequest(
                    kind="workflow",
                    name="test-workflow",
                ),
                LlmObsSpanRequest(
                    kind="workflow",
                    name="test-workflow-2",
                ),
            ],
        )

        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 2

        workflow_span_event, workflow_span_2_event = span_events

        assert workflow_span_event["name"] == "test-workflow"
        assert workflow_span_2_event["name"] == "test-workflow-2"
        assert workflow_span_event["parent_id"] == "undefined"
        assert workflow_span_2_event["parent_id"] == "undefined"

    def test_ml_app_propagates_to_children(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="workflow",
            ml_app="overridden-ml-app",
            children=[
                LlmObsSpanRequest(
                    kind="task",
                    ml_app="overridden-ml-app-2",
                ),
                LlmObsSpanRequest(
                    kind="task",
                ),
            ],
        )

        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 3

        parent_workflow_span_event, child_task_span_event, child_task_span_2_event = span_events
        assert find_event_tag(parent_workflow_span_event, "ml_app") == "overridden-ml-app"
        assert find_event_tag(child_task_span_event, "ml_app") == "overridden-ml-app-2"
        assert find_event_tag(child_task_span_2_event, "ml_app") == "overridden-ml-app"

    def test_session_id_propagates_to_children(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="workflow",
            session_id="overridden-session-id",
            children=[
                LlmObsSpanRequest(
                    kind="task",
                    session_id="overridden-session-id-2",
                ),
                LlmObsSpanRequest(
                    kind="task",
                ),
            ],
        )

        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 3

        parent_workflow_span_event, child_task_span_event, child_task_span_2_event = span_events
        assert find_event_tag(parent_workflow_span_event, "session_id") == "overridden-session-id"
        assert find_event_tag(child_task_span_event, "session_id") == "overridden-session-id-2"
        assert find_event_tag(child_task_span_2_event, "session_id") == "overridden-session-id"

    def test_session_id_propagates_through_apm_spans(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="workflow",
            session_id="test-session-id",
            children=[
                ApmSpanRequest(
                    name="apm-span",
                    children=[
                        LlmObsSpanRequest(
                            kind="task",
                        )
                    ],
                )
            ],
        )

        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 2

        workflow_span_event, task_span_event = span_events
        assert find_event_tag(workflow_span_event, "session_id") == "test-session-id"
        assert find_event_tag(task_span_event, "session_id") == "test-session-id"
