from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, NotRequired, TypedDict


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


class DatasetRecordRequest(TypedDict, total=False):
    """A single record in a dataset."""

    input_data: dict[str, Any]
    expected_output: Any
    metadata: dict[str, Any]


class DatasetCreateRequest(TypedDict, total=False):
    """Request to create a new dataset."""

    dataset_name: str
    description: str
    records: list[DatasetRecordRequest]
    project_name: str


class DatasetDeleteRequest(TypedDict):
    """Request to delete a dataset."""

    dataset_id: str


class DatasetResponse(TypedDict, total=False):
    """Response from dataset operations."""

    dataset_id: str
    name: str
    description: str
    project_name: str
    project_id: str
    version: int
    latest_version: int
    records: list[dict[str, Any]]
