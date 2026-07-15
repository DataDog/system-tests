from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict


LlmObsExportKind = Literal["llm", "agent", "workflow", "task", "step", "tool", "embedding", "retrieval"]
LlmObsExportMetricType = Literal["categorical", "score", "boolean", "json"]


@dataclass
class SpanRequest:
    sdk: Literal["tracer", "llmobs"]
    name: str | None = None
    children: list[LlmObsAnnotationContextRequest | LlmObsSpanRequest] | None = None

    annotations: list[LlmObsAnnotationRequest] | None = None
    annotate_after: bool | None = None
    export_span: Literal["explicit", "implicit"] | None = None

    type: Literal["span"] = "span"


@dataclass
class ApmSpanRequest(SpanRequest):
    name: str | None = None
    sdk: Literal["tracer"] = "tracer"


@dataclass
class LlmObsSpanRequest(SpanRequest):
    kind: Literal["llm", "agent", "workflow", "task", "tool", "embedding", "retrieval"] | None = None
    session_id: str | None = None
    ml_app: str | None = None
    model_name: str | None = None
    model_provider: str | None = None
    sdk: Literal["llmobs"] = "llmobs"


@dataclass
class LlmObsAnnotationRequest:
    input_data: dict | str | list[dict | str] | None = None
    output_data: dict | str | list[dict | str] | None = None
    metadata: dict | None = None
    metrics: dict | None = None
    tags: dict | None = None
    cost_tags: list | None = None
    prompt: dict | None = None

    explicit_span: bool | None = False


@dataclass
class LlmObsAnnotationContextRequest:
    prompt: dict | None = None
    name: str | None = None
    tags: dict | None = None
    cost_tags: list | None = None

    children: list[LlmObsAnnotationContextRequest | LlmObsSpanRequest] | None = None
    type: Literal["annotation_context"] = "annotation_context"


@dataclass
class LlmObsExportSpanLinkRequest:
    trace_id: str
    span_id: str
    trace_id_high: int = 0
    attributes: dict[str, str] | None = None
    tracestate: str = ""
    flags: int = 0


@dataclass
class LlmObsExportErrorRequest:
    type: str
    message: str
    stack: str


@dataclass
class LlmObsExportSpanRequest:
    trace_id: str
    span_id: str
    kind: LlmObsExportKind
    start_ns: int
    duration_ns: int
    parent_id: str = ""
    session_id: str = ""
    name: str = ""
    service: str = ""
    model_name: str = ""
    model_provider: str = ""
    input: str = ""
    output: str = ""
    metadata: dict[str, Any] | None = None
    metrics: dict[str, float] | None = None
    tags: list[str] | None = None
    span_links: list[LlmObsExportSpanLinkRequest] | None = None
    apm_trace_id: str = ""
    error: LlmObsExportErrorRequest | None = None


@dataclass
class LlmObsExportEvaluationRequest:
    label: str
    span_id: str = ""
    trace_id: str = ""
    tag_key: str = ""
    tag_value: str = ""
    metric_type: LlmObsExportMetricType | None = None
    categorical_value: str | None = None
    score_value: float | None = None
    boolean_value: bool | None = None
    json_value: dict[str, Any] | None = None
    tags: list[str] | None = None
    ml_app: str = ""
    timestamp_ms: int = 0
    assessment: str = ""
    reasoning: str = ""
    metadata: dict[str, Any] | None = None


@dataclass
class LlmObsExportRequest:
    ml_app: str
    service: str = ""
    env: str = ""
    version: str = ""
    call_service: str = ""
    call_ml_app: str = ""
    spans: list[LlmObsExportSpanRequest] = field(default_factory=list)
    evaluations: list[LlmObsExportEvaluationRequest] = field(default_factory=list)


class LlmObsExportSubmissionResult(TypedDict):
    sent: int
    dropped: int
    failed: int


class LlmObsExportResponse(TypedDict):
    spans: LlmObsExportSubmissionResult
    evaluations: LlmObsExportSubmissionResult


class DatasetRecordRequest(TypedDict, total=False):
    input_data: dict[str, Any]
    expected_output: Any
    metadata: dict[str, Any]


class DatasetCreateRequest(TypedDict, total=False):
    dataset_name: str
    description: str
    records: list[DatasetRecordRequest]
    project_name: str


class DatasetResponse(TypedDict, total=False):
    dataset_id: str
    name: str
    description: str
    project_name: str
    project_id: str
    version: int
    latest_version: int
    records: list[dict[str, Any]]
