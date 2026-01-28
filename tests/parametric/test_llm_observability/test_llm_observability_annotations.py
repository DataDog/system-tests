from requests import HTTPError
from tests.parametric.test_llm_observability.utils import find_event_tag, get_io_value_from_span_event
from utils import scenarios
from utils.docker_fixtures import TestAgentAPI
from ..conftest import APMLibrary  # noqa: TID252
from utils.docker_fixtures.spec.llm_observability import (
    LlmObsAnnotationRequest,
    LlmObsSpanRequest,
    ApmSpanRequest,
)

import pytest


@scenarios.parametric
class Test_Annotations:
    def test_annotate_no_span_throws(self, test_library: APMLibrary):
        trace_structure = ApmSpanRequest(
            name="apm-span",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data="hello",
                    output_data="world",
                )
            ],
        )
        with pytest.raises(HTTPError):
            test_library.llmobs_trace(trace_structure)

    def test_annotate_non_llmobs_span_throws(self, test_library: APMLibrary):
        trace_structure = ApmSpanRequest(
            name="apm-span",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data="hello",
                    output_data="world",
                    explicit_span=True,
                )
            ],
        )
        with pytest.raises(HTTPError):
            test_library.llmobs_trace(trace_structure)

    def test_annotate_finished_span_throws(self, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="task",
            name="test-task",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data="hello",
                    output_data="world",
                )
            ],
            annotate_after=True,
        )
        with pytest.raises(HTTPError):
            test_library.llmobs_trace(trace_structure)

    def test_annotate_non_model_span(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="task",
            name="test-task",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data="hello",
                    output_data="world",
                    tags={"foo": "bar"},
                )
            ],
        )
        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        span_event = span_events[0]

        assert get_io_value_from_span_event(span_event, "input", "value") == "hello"
        assert get_io_value_from_span_event(span_event, "output", "value") == "world"
        assert find_event_tag(span_event, "foo") == "bar"

    def test_annotate_llm_span_simple(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="llm",
            name="test-llm",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data="hello",
                    output_data="world",
                )
            ],
        )
        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        span_event = span_events[0]

        input_messages = get_io_value_from_span_event(span_event, "input", "messages")
        output_messages = get_io_value_from_span_event(span_event, "output", "messages")

        assert len(input_messages) == 1
        assert input_messages[0]["content"] == "hello"
        assert input_messages[0]["role"] == ""

        assert len(output_messages) == 1
        assert output_messages[0]["content"] == "world"
        assert output_messages[0]["role"] == ""

    def test_annotate_llm_span_with_messages(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="llm",
            name="test-llm",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data=[
                        {"role": "user", "content": "hello"},
                        {"role": "assistant", "content": "world"},
                        {"role": "user", "content": "foo"},
                    ],
                    output_data=[
                        {"role": "assistant", "content": "bar"},
                    ],
                )
            ],
        )

        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        span_event = span_events[0]

        assert get_io_value_from_span_event(span_event, "input", "messages") == [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
            {"role": "user", "content": "foo"},
        ]
        assert get_io_value_from_span_event(span_event, "output", "messages") == [
            {"role": "assistant", "content": "bar"},
        ]

    def test_annotate_llm_span_with_malformed_messages_throws(self, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="llm",
            name="test-llm",
            annotations=[LlmObsAnnotationRequest(input_data=[{"content": "hello", "role": 5}])],
        )

        with pytest.raises(HTTPError):
            test_library.llmobs_trace(trace_structure)

    def test_annotate_embedding_span_simple(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="embedding",
            name="test-embedding",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data="hello",
                    output_data="world",
                )
            ],
        )

        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        span_event = span_events[0]

        assert get_io_value_from_span_event(span_event, "input", "documents") == [{"text": "hello"}]
        assert get_io_value_from_span_event(span_event, "output", "value") == "world"

    def test_annotate_embedding_span_with_documents(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="embedding",
            name="test-embedding",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data=[
                        {"text": "hello", "name": "foo", "id": "bar", "score": 0.678},
                        {"text": "world", "name": "baz", "score": 0.321},
                    ],
                    output_data="embedded 2 documents",
                )
            ],
        )

        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        span_event = span_events[0]

        assert get_io_value_from_span_event(span_event, "input", "documents") == [
            {"text": "hello", "name": "foo", "id": "bar", "score": 0.678},
            {"text": "world", "name": "baz", "score": 0.321},
        ]
        assert get_io_value_from_span_event(span_event, "output", "value") == "embedded 2 documents"

    def test_annotate_embedding_span_with_malformed_documents_throws(self, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="embedding",
            name="test-embedding",
            annotations=[LlmObsAnnotationRequest(input_data=[{"text": 5}])],
        )

        with pytest.raises(HTTPError):
            test_library.llmobs_trace(trace_structure)

    def test_annotate_retrieval_span_simple(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="retrieval",
            name="test-retrieval",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data="hello",
                    output_data="world",
                )
            ],
        )

        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        span_event = span_events[0]

        assert get_io_value_from_span_event(span_event, "input", "value") == "hello"
        assert get_io_value_from_span_event(span_event, "output", "documents") == [{"text": "world"}]

    def test_annotate_retrieval_span_with_documents(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="retrieval",
            name="test-retrieval",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data="hello",
                    output_data=[
                        {"text": "world", "name": "foo", "id": "bar", "score": 0.678},
                        {"text": "foo", "name": "baz", "score": 0.321},
                    ],
                )
            ],
        )

        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        span_event = span_events[0]

        assert get_io_value_from_span_event(span_event, "input", "value") == "hello"
        assert get_io_value_from_span_event(span_event, "output", "documents") == [
            {"text": "world", "name": "foo", "id": "bar", "score": 0.678},
            {"text": "foo", "name": "baz", "score": 0.321},
        ]

    def test_annotate_retrieval_span_with_malformed_documents_throws(self, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="retrieval",
            name="test-retrieval",
            annotations=[LlmObsAnnotationRequest(output_data=[{"text": 5}])],
        )

        with pytest.raises(HTTPError):
            test_library.llmobs_trace(trace_structure)

    def test_annotate_merges_and_updates_metadata(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="task",
            name="test-task",
            annotations=[
                LlmObsAnnotationRequest(metadata={"foo": "bar"}),
                LlmObsAnnotationRequest(metadata={"foo": "quux", "bar": "baz"}),
            ],
        )

        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        span_event = span_events[0]

        assert span_event["meta"]["metadata"]["foo"] == "quux"
        assert span_event["meta"]["metadata"]["bar"] == "baz"

    def test_annotate_merges_and_updates_metrics(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="task",
            name="test-task",
            annotations=[
                LlmObsAnnotationRequest(metrics={"foo": 5}),
                LlmObsAnnotationRequest(metrics={"foo": 10, "bar": 20}),
            ],
        )

        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        span_event = span_events[0]

        assert span_event["metrics"]["foo"] == 10
        assert span_event["metrics"]["bar"] == 20

    def test_annotate_merges_and_updates_tags(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        trace_structure = LlmObsSpanRequest(
            kind="task",
            name="test-task",
            annotations=[
                LlmObsAnnotationRequest(tags={"foo": "bar"}),
                LlmObsAnnotationRequest(tags={"baz": "qux", "foo": "quux"}),
            ],
        )
        test_library.llmobs_trace(trace_structure)
        span_events = test_agent.wait_for_llmobs_requests(num=1)
        assert len(span_events) == 1
        span_event = span_events[0]

        assert find_event_tag(span_event, "foo") == "quux"
        assert find_event_tag(span_event, "baz") == "qux"
