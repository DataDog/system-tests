from ddtrace.internal.telemetry import telemetry_writer
from ddtrace.llmobs import LLMObs
from ddtrace import tracer

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Union, List, Literal
import asyncio

router = APIRouter()


class AnnotationRequest(BaseModel):
    input_data: Optional[Union[List[Union[dict, str]], dict, str]] = None
    output_data: Optional[Union[List[Union[dict, str]], dict, str]] = None
    metadata: Optional[dict] = None
    metrics: Optional[dict] = None
    tags: Optional[dict] = None

    explicit_span: Optional[bool] = False


class TraceStructureRequest(BaseModel):
    sdk: Union[Literal["llmobs", "tracer"]]

    name: Optional[str] = None
    session_id: Optional[str] = None
    ml_app: Optional[str] = None
    model_name: Optional[str] = None
    model_provider: Optional[str] = None
    kind: Optional[str] = None

    annotations: Optional[List[AnnotationRequest]] = None
    annotate_after: Optional[bool] = False

    children: Optional[List[Union["TraceStructureRequest", List["TraceStructureRequest"]]]] = None

    export_span: Optional[Literal["explicit", "implicit"]] = None


class Request(BaseModel):
    trace_structure_request: TraceStructureRequest


async def create_trace(trace_structure_request: TraceStructureRequest) -> dict:
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
            if not isinstance(child, list):
                await create_trace(child)
            else:
                await asyncio.gather(*[create_trace(c) for c in child])

    if annotate_after:
        # this case should always throw
        apply_annotations(span, annotations, annotate_after=True)

    return exported_span_ctx


def apply_annotations(span, annotations: AnnotationRequest, annotate_after=False):
    for annotation in annotations:
        options = {k: v for k, v in annotation.dict().items() if k not in ("explicit_span",)}
        if annotation.explicit_span or annotate_after:
            options["span"] = span
        LLMObs.annotate(**options)


@router.post("/llm_observability/trace")
async def llmobs_trace(trace_structure_request: Request):
    try:
        maybe_exported_span_ctx = await create_trace(trace_structure_request.trace_structure_request)
        return maybe_exported_span_ctx or {}
    finally:
        telemetry_writer.periodic(force_flush=True)
