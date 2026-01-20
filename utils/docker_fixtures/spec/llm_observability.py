from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


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
    prompt: dict | None = None

    explicit_span: bool | None = False


@dataclass
class LlmObsAnnotationContextRequest:
    prompt: dict | None = None
    name: str | None = None
    tags: dict | None = None

    children: list[LlmObsAnnotationContextRequest | LlmObsSpanRequest] | None = None
    type: Literal["annotation_context"] = "annotation_context"


# =============================================================================
# Datasets and Experiments (DNE) Spec Types
# =============================================================================


@dataclass
class DatasetRecordRequest:
    """A single record in a dataset."""

    input_data: dict[str, Any]
    expected_output: Any | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class DatasetCreateRequest:
    """Request to create a new dataset."""

    dataset_name: str
    description: str | None = None
    records: list[DatasetRecordRequest] | None = None
    project_name: str | None = None


@dataclass
class DatasetDeleteRequest:
    """Request to delete a dataset."""

    dataset_id: str


@dataclass
class DatasetResponse:
    """Response from dataset operations."""

    dataset_id: str
    name: str
    description: str | None = None
    project_name: str | None = None
    project_id: str | None = None
    version: int | None = None
    latest_version: int | None = None
    records: list[dict[str, Any]] = field(default_factory=list)
