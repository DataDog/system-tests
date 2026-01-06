from dataclasses import dataclass
from typing import Literal


@dataclass
class ApmSpanRequest:
    name: str
    sdk: Literal["tracer"] = "tracer"


@dataclass
class LlmObsSpanRequest:
    kind: Literal["llm", "agent", "workflow", "task", "tool", "embedding", "retrieval"]
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

    explicit_span: bool | None = False


@dataclass
class SpanRequest:
    sdk: Literal["tracer", "llmobs"]
    name: str | None = None
    children: list[ApmSpanRequest | LlmObsSpanRequest] | list[list[ApmSpanRequest | LlmObsSpanRequest]] | None = None

    annotations: list[LlmObsAnnotationRequest] | None = None
    annotate_after: bool | None = None
    export_span: Literal["explicit", "implicit"] | None = None
