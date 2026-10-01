import time
from typing import Any, cast

from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.spec.llm_observability import (
    LlmObsExportErrorRequest,
    LlmObsExportEvaluationRequest,
    LlmObsExportKind,
    LlmObsExportRequest,
    LlmObsExportSpanLinkRequest,
    LlmObsExportSpanRequest,
)
from ..conftest import APMLibrary  # noqa: TID252


SPAN_KINDS: tuple[LlmObsExportKind, ...] = (
    "llm",
    "agent",
    "workflow",
    "task",
    "step",
    "tool",
    "embedding",
    "retrieval",
)


@features.llm_observability_sdk_enablement
@scenarios.parametric
class Test_Offline_Export:
    def test_span_contract(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        spans = [
            LlmObsExportSpanRequest(
                trace_id="trace-offline-123",
                span_id="span-offline-456",
                parent_id="parent-offline-789",
                session_id="session-offline-123",
                name="offline-chat",
                service="span-service",
                kind="llm",
                start_ns=1_700_000_000_123_456_789,
                duration_ns=42_000_000,
                model_name="gpt-4o",
                model_provider="OpenAI",
                input="hello",
                output="hi there",
                metadata={"temperature": 0.7, "nested": {"enabled": True}},
                metrics={"input_tokens": 10, "output_tokens": 5},
                tags=["custom:value"],
                span_links=[
                    LlmObsExportSpanLinkRequest(
                        trace_id="18446744073709551615",
                        trace_id_high=9_223_372_036_854_775_808,
                        span_id="42",
                        attributes={"reason": "offline-parent"},
                        tracestate="dd=s:1",
                        flags=1,
                    )
                ],
                apm_trace_id="apm-trace-123",
                error=LlmObsExportErrorRequest(
                    type="provider_error",
                    message="upstream refused",
                    stack="stack trace",
                ),
            )
        ]
        spans.extend(
            LlmObsExportSpanRequest(
                trace_id=f"trace-{kind}",
                span_id=f"span-{kind}",
                kind=kind,
                start_ns=1_700_000_000_123_456_789 + index,
                duration_ns=1,
            )
            for index, kind in enumerate(SPAN_KINDS[1:], start=1)
        )

        response = test_library.llmobs_export(
            LlmObsExportRequest(
                ml_app="test-app",
                service="client-service",
                env="test-env",
                version="test-version",
                call_service="call-service",
                spans=spans,
            )
        )

        assert response["spans"] == {"sent": len(SPAN_KINDS), "dropped": 0, "failed": 0}
        envelopes = cast(
            "list[dict[str, Any]]",
            test_agent.wait_for_llmobs_requests(num=1, sort_by_start=False),
        )
        assert len(envelopes) == len(SPAN_KINDS)
        for envelope in envelopes:
            assert set(envelope) == {"_dd.stage", "_dd.tracer_version", "event_type", "spans"}
            assert envelope["_dd.stage"] == "raw"
            assert envelope["event_type"] == "span"
            assert envelope["_dd.tracer_version"]
            assert len(envelope["spans"]) == 1

        spans_by_kind = {envelope["spans"][0]["meta"]["span.kind"]: envelope["spans"][0] for envelope in envelopes}
        assert set(spans_by_kind) == set(SPAN_KINDS)

        llm_span = spans_by_kind["llm"]
        assert llm_span["trace_id"] == "trace-offline-123"
        assert llm_span["span_id"] == "span-offline-456"
        assert llm_span["parent_id"] == "parent-offline-789"
        assert llm_span["session_id"] == "session-offline-123"
        assert llm_span["name"] == "offline-chat"
        assert llm_span["service"] == "span-service"
        assert llm_span["start_ns"] == 1_700_000_000_123_456_789
        assert llm_span["duration"] == 42_000_000
        assert llm_span["status"] == "error"
        assert llm_span["metrics"] == {"input_tokens": 10, "output_tokens": 5}
        assert llm_span["_dd"] == {
            "span_id": "span-offline-456",
            "trace_id": "trace-offline-123",
            "apm_trace_id": "apm-trace-123",
        }

        meta = llm_span["meta"]
        assert meta == {
            "span.kind": "llm",
            "model_name": "gpt-4o",
            "model_provider": "openai",
            "input": {"value": "hello"},
            "output": {"value": "hi there"},
            "metadata": {"temperature": 0.7, "nested": {"enabled": True}},
            "error.type": "provider_error",
            "error.message": "upstream refused",
            "error.stack": "stack trace",
        }
        assert {
            "custom:value",
            "ml_app:test-app",
            "env:test-env",
            "version:test-version",
            "service:span-service",
            "source:integration",
            "language:go",
            "error:1",
        }.issubset(set(llm_span["tags"]))
        assert any(tag.startswith("ddtrace.version:") for tag in llm_span["tags"])
        assert llm_span["span_links"] == [
            {
                "trace_id": "18446744073709551615",
                "trace_id_high": 9_223_372_036_854_775_808,
                "span_id": "42",
                "attributes": {"reason": "offline-parent"},
                "tracestate": "dd=s:1",
                "flags": 1,
            }
        ]

        step_span = spans_by_kind["step"]
        assert step_span["name"] == "step"
        assert step_span["parent_id"] == "undefined"
        assert step_span["service"] == "call-service"
        assert "service:call-service" in step_span["tags"]
        assert step_span["status"] == "ok"

    def test_evaluation_contract(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        timestamp_ms = int(time.time() * 1000)
        response = test_library.llmobs_export(
            LlmObsExportRequest(
                ml_app="client-app",
                call_ml_app="call-app",
                evaluations=[
                    LlmObsExportEvaluationRequest(
                        span_id="span-offline-456",
                        trace_id="trace-offline-123",
                        label="quality",
                        metric_type="score",
                        score_value=0.9,
                        tags=["judge:test"],
                        timestamp_ms=timestamp_ms,
                        assessment="mostly correct",
                        reasoning="grounded in the supplied context",
                        metadata={"judge": "gpt-4o", "rubric_version": 3},
                    ),
                    LlmObsExportEvaluationRequest(
                        span_id="span-json",
                        trace_id="trace-json",
                        label="structured-quality",
                        metric_type="json",
                        json_value={"score": 0.95, "reasons": ["grounded", "concise"]},
                        ml_app="row-app",
                        timestamp_ms=timestamp_ms,
                    ),
                ],
            )
        )

        assert response["evaluations"] == {"sent": 2, "dropped": 0, "failed": 0}
        requests = cast(
            "list[dict[str, Any]]",
            test_agent.wait_for_llmobs_evaluations_requests(num=1),
        )
        assert len(requests) == 1
        assert requests[0]["data"]["type"] == "evaluation_metric"
        metrics = requests[0]["data"]["attributes"]["metrics"]
        assert len(metrics) == 2

        score_metric = metrics[0]
        assert score_metric["join_on"] == {"span": {"span_id": "span-offline-456", "trace_id": "trace-offline-123"}}
        assert score_metric["label"] == "quality"
        assert score_metric["metric_type"] == "score"
        assert score_metric["score_value"] == 0.9
        assert score_metric["ml_app"] == "call-app"
        assert score_metric["timestamp_ms"] == timestamp_ms
        assert score_metric["assessment"] == "mostly correct"
        assert score_metric["reasoning"] == "grounded in the supplied context"
        assert score_metric["metadata"] == {"judge": "gpt-4o", "rubric_version": 3}
        assert "judge:test" in score_metric["tags"]
        assert any(tag.startswith("ddtrace.version:") for tag in score_metric["tags"])

        json_metric = metrics[1]
        assert json_metric["metric_type"] == "json"
        assert json_metric["json_value"] == {"score": 0.95, "reasons": ["grounded", "concise"]}
        assert json_metric["ml_app"] == "row-app"
