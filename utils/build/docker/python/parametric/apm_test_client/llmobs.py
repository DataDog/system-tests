from __future__ import annotations

from ddtrace.internal.telemetry import telemetry_writer
from ddtrace.llmobs import LLMObs
from ddtrace.llmobs._experiment import DatasetRecord
from ddtrace import tracer

from fastapi import APIRouter
from pydantic import BaseModel
from pydantic.dataclasses import dataclass
from typing import Any, Literal, Union

router = APIRouter()


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


# Update forward references for circular dependencies
ApmSpanRequest.__pydantic_model__.update_forward_refs()
LlmObsSpanRequest.__pydantic_model__.update_forward_refs()
LlmObsAnnotationContextRequest.__pydantic_model__.update_forward_refs()


class Request(BaseModel):
    trace_structure_request: Union[LlmObsAnnotationContextRequest, LlmObsSpanRequest, ApmSpanRequest]


def create_trace(trace_structure_request: SpanRequest | LlmObsAnnotationContextRequest) -> dict:
    type = trace_structure_request.type
    if type == "annotation_context":
        options = {}
        if trace_structure_request.prompt:
            options["prompt"] = trace_structure_request.prompt
        if trace_structure_request.name:
            options["name"] = trace_structure_request.name
        if trace_structure_request.tags:
            options["tags"] = trace_structure_request.tags

        with LLMObs.annotation_context(**options):
            children = trace_structure_request.children
            if not isinstance(children, list):
                return

            exported_span_ctx = None
            for child in children:
                maybe_exported_span_ctx = create_trace(child)
                if maybe_exported_span_ctx and not exported_span_ctx:
                    exported_span_ctx = maybe_exported_span_ctx

            return exported_span_ctx

    is_llmobs = trace_structure_request.sdk == "llmobs"
    kind = trace_structure_request.kind if is_llmobs else None
    make_trace = getattr(LLMObs, kind) if is_llmobs else tracer.trace

    if is_llmobs:
        options = {
            "name": trace_structure_request.name,
        }
        if trace_structure_request.session_id:
            options["session_id"] = trace_structure_request.session_id
        if trace_structure_request.ml_app:
            options["ml_app"] = trace_structure_request.ml_app
        if trace_structure_request.model_name:
            options["model_name"] = trace_structure_request.model_name
        if trace_structure_request.model_provider:
            options["model_provider"] = trace_structure_request.model_provider
    else:
        options = {
            "name": trace_structure_request.name,
        }

    exported_span_ctx = None

    annotations = trace_structure_request.annotations
    annotate_after = trace_structure_request.annotate_after
    span = None

    with make_trace(**options) as _span:
        span = _span

        # apply annotations
        if annotations and not annotate_after:
            apply_annotations(span, annotations)

        # apply export span
        export_span = trace_structure_request.export_span
        if export_span:
            args = (span,) if export_span == "explicit" else ()
            exported_span_ctx = LLMObs.export_span(*args)

        # trace children
        children = trace_structure_request.children or []

        for child in children:
            create_trace(child)

    if annotate_after:
        # this case should always throw
        apply_annotations(span, annotations, annotate_after=True)

    return exported_span_ctx


def apply_annotations(span, annotations: list[LlmObsAnnotationRequest], annotate_after=False):
    for annotation in annotations:
        options = {
            field_name: getattr(annotation, field_name)
            for field_name in annotation.__dataclass_fields__
            if field_name != "explicit_span"
        }
        if annotation.explicit_span or annotate_after:
            options["span"] = span
        LLMObs.annotate(**options)


@router.post("/llm_observability/trace")
def llmobs_trace(trace_structure_request: Request):
    try:
        maybe_exported_span_ctx = create_trace(trace_structure_request.trace_structure_request)
        return maybe_exported_span_ctx or {}
    finally:
        telemetry_writer.periodic(force_flush=True)


@dataclass
class DatasetRecordRequest:
    """A single record in a dataset."""

    input_data: dict
    expected_output: Any | None = None
    metadata: dict | None = None


@dataclass
class DatasetCreateRequest:
    """Request to create a new dataset."""

    dataset_name: str
    description: str | None = None
    records: list[DatasetRecordRequest] | None = None
    project_name: str | None = None


class DatasetCreateRequestModel(BaseModel):
    dataset_create_request: DatasetCreateRequest


@dataclass
class DatasetDeleteRequest:
    """Request to delete a dataset."""

    dataset_id: str


class DatasetDeleteRequestModel(BaseModel):
    dataset_delete_request: DatasetDeleteRequest


@router.post("/llm_observability/dataset/create")
def llmobs_dataset_create(request: DatasetCreateRequestModel):
    """Create a new dataset."""
    req = request.dataset_create_request

    # Convert records to DatasetRecord format if provided
    records = None
    if req.records:
        records = [
            DatasetRecord(
                input_data=r.input_data,
                expected_output=r.expected_output,
                metadata=r.metadata or {},
            )
            for r in req.records
        ]

    # Build kwargs for create_dataset
    kwargs = {
        "dataset_name": req.dataset_name,
    }
    if req.description is not None:
        kwargs["description"] = req.description
    if records is not None:
        kwargs["records"] = records
    if req.project_name is not None:
        kwargs["project_name"] = req.project_name

    dataset = LLMObs.create_dataset(**kwargs)

    # Build response
    return {
        "dataset_id": dataset._id,
        "name": dataset.name,
        "description": dataset.description,
        "project_name": dataset.project.get("name") if dataset.project else None,
        "project_id": dataset.project.get("_id") if dataset.project else None,
        "version": dataset._version,
        "latest_version": dataset._latest_version,
        "records": list(dataset._records),
    }


@router.post("/llm_observability/dataset/delete")
def llmobs_dataset_delete(request: DatasetDeleteRequestModel):
    """Delete a dataset."""
    req = request.dataset_delete_request
    LLMObs._delete_dataset(dataset_id=req.dataset_id)
    return {"success": True}
