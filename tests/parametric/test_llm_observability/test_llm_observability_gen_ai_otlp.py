import base64
import json
import time
from typing import TypedDict, cast

import pytest

from utils import scenarios, features
from utils.docker_fixtures import TestAgentAPI
from ..conftest import APMLibrary  # noqa: TID252
from utils.docker_fixtures.spec.llm_observability import (
    LlmObsSpanRequest,
    LlmObsAnnotationRequest,
)


type Headers = dict[str, str]
type LibraryEnvironment = dict[str, str | bool]
type OtlpAttributeScalar = str | bool | int | float | None
type OtlpAttributes = dict[str, OtlpAttributeScalar]


class OtlpAttributeValue(TypedDict, total=False):
    stringValue: str
    boolValue: bool
    intValue: str | int
    doubleValue: float | str


class OtlpAttribute(TypedDict):
    key: str
    value: OtlpAttributeValue


class OtlpSpan(TypedDict, total=False):
    attributes: list[OtlpAttribute]


class OtlpScopeSpans(TypedDict, total=False):
    spans: list[OtlpSpan]


class OtlpResource(TypedDict, total=False):
    attributes: list[OtlpAttribute]


class OtlpResourceSpans(TypedDict, total=False):
    resource: OtlpResource
    scopeSpans: list[OtlpScopeSpans]


class OtlpTraceBody(TypedDict, total=False):
    resourceSpans: list[OtlpResourceSpans]


class CapturedRawOtlpRequest(TypedDict):
    url: str
    headers: Headers
    body: str


class DecodedOtlpTraceRequest(TypedDict):
    headers: Headers
    body: OtlpTraceBody


class GenAiChatCapture(TypedDict):
    headers: Headers
    resource_attributes: OtlpAttributes
    span_attributes: OtlpAttributes


class GenAiMessage(TypedDict):
    role: str
    content: str


class GenAiMetadata(TypedDict):
    temperature: float


INVALID_TARGET_METADATA_CASES: tuple[tuple[Headers, str, str], ...] = (
    ({"dd-ml-app": "test-app"}, "test-service", "dd-otlp-source=llmobs"),
    (
        {"dd-otlp-source": "llmobs", "dd-ml-app": "wrong-app"},
        "test-service",
        "dd-ml-app=test-app",
    ),
    (
        {"dd-otlp-source": "llmobs", "dd-ml-app": "test-app"},
        "wrong-service",
        "service.name=test-service",
    ),
)


@pytest.fixture
def llmobs_ml_app() -> str:
    return "test-app"


@pytest.fixture
def llmobs_gen_ai_otlp_library_env(library_env: LibraryEnvironment, test_agent: TestAgentAPI) -> LibraryEnvironment:
    library_env["OTEL_TRACES_EXPORTER"] = "otlp"
    # The test agent must capture JSON-decodable OTLP payloads.
    library_env["OTEL_EXPORTER_OTLP_TRACES_PROTOCOL"] = "http/json"
    library_env["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = f"http://{test_agent.container_name}:4318/v1/traces"
    library_env["OTEL_EXPORTER_OTLP_TRACES_HEADERS"] = "dd-otlp-source=llmobs,dd-ml-app=test-app"
    library_env["DD_API_KEY"] = "<not-a-real-key>"
    return library_env


def _attr_value(item: OtlpAttribute) -> OtlpAttributeScalar:
    value = item["value"]
    if "stringValue" in value:
        return value["stringValue"]
    if "boolValue" in value:
        return value["boolValue"]
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return value["doubleValue"]
    return None


def _attribute_map(attributes: list[OtlpAttribute]) -> OtlpAttributes:
    return {item["key"]: _attr_value(item) for item in attributes}


def _otlp_trace_bodies(test_agent: TestAgentAPI) -> list[DecodedOtlpTraceRequest]:
    out: list[DecodedOtlpTraceRequest] = []
    raw_requests = cast("list[CapturedRawOtlpRequest]", test_agent.otlp_requests())
    for request in raw_requests:
        if not request["url"].endswith("/v1/traces"):
            continue
        headers: Headers = {name.lower(): value for name, value in request["headers"].items()}
        body = cast("OtlpTraceBody", json.loads(base64.b64decode(request["body"]).decode("utf-8")))
        out.append({"headers": headers, "body": body})
    return out


def _wait_for_otlp_trace_spans(test_agent: TestAgentAPI, *, deadline_s: float = 20.0) -> list[DecodedOtlpTraceRequest]:
    deadline = time.monotonic() + deadline_s
    captured: list[DecodedOtlpTraceRequest] = []
    while time.monotonic() < deadline:
        captured = _otlp_trace_bodies(test_agent)
        for request in captured:
            body = request["body"]
            for rs in body.get("resourceSpans", []):
                for ss in rs.get("scopeSpans", []):
                    if ss.get("spans"):
                        return captured
        time.sleep(0.2)
    raise AssertionError("No OTLP /v1/traces spans captured before deadline")


def _find_gen_ai_chat_capture(captured: list[DecodedOtlpTraceRequest]) -> GenAiChatCapture:
    for request in captured:
        for resource_spans in request["body"].get("resourceSpans", []):
            resource_attributes = _attribute_map(resource_spans.get("resource", {}).get("attributes", []))
            for scope_spans in resource_spans.get("scopeSpans", []):
                for span in scope_spans.get("spans", []):
                    span_attributes = _attribute_map(span.get("attributes", []))
                    if span_attributes.get("gen_ai.operation.name") == "chat":
                        return {
                            "headers": request["headers"],
                            "resource_attributes": resource_attributes,
                            "span_attributes": span_attributes,
                        }
    raise AssertionError("No captured span with gen_ai.operation.name=chat")


def _validated_gen_ai_chat_span(captured: list[DecodedOtlpTraceRequest]) -> OtlpAttributes:
    match = _find_gen_ai_chat_capture(captured)
    headers = match["headers"]
    resource_attributes = match["resource_attributes"]

    assert headers.get("dd-otlp-source") == "llmobs", "Expected matching OTLP request dd-otlp-source=llmobs"
    assert headers.get("dd-ml-app") == "test-app", "Expected matching OTLP request dd-ml-app=test-app"
    assert resource_attributes.get("service.name") == "test-service", (
        "Expected matching OTLP resource service.name=test-service"
    )
    return match["span_attributes"]


def _synthetic_trace_request(*, headers: Headers, service_name: str, operation_name: str) -> DecodedOtlpTraceRequest:
    return {
        "headers": headers,
        "body": {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": service_name}},
                        ]
                    },
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "attributes": [
                                        {
                                            "key": "gen_ai.operation.name",
                                            "value": {"stringValue": operation_name},
                                        }
                                    ]
                                }
                            ]
                        }
                    ],
                }
            ]
        },
    }


@features.llm_observability_sdk_enablement
@scenarios.parametric
class Test_GenAI_OTLP:
    """Assert the emitted gen_ai OTLP schema without backend read-back."""

    def test_llm_span_gen_ai_attributes(
        self,
        llmobs_gen_ai_otlp_library_env: LibraryEnvironment,  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        req = LlmObsSpanRequest(
            kind="llm",
            name="chat",
            model_name="gpt-4o",
            model_provider="openai",
            session_id="session-123",
            export_span="explicit",
            annotations=[
                LlmObsAnnotationRequest(
                    input_data=[{"role": "user", "content": "hello"}],
                    output_data=[{"role": "assistant", "content": "hi there"}],
                    metadata={"temperature": 0.7},
                    metrics={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                )
            ],
        )
        with test_library as t:
            t.llmobs_trace(req)

        captured = _wait_for_otlp_trace_spans(test_agent)
        gen_ai_span = _validated_gen_ai_chat_span(captured)

        assert gen_ai_span["gen_ai.operation.name"] == "chat"
        assert gen_ai_span["gen_ai.request.model"] == "gpt-4o"
        assert gen_ai_span["gen_ai.provider.name"] == "openai"
        assert gen_ai_span["gen_ai.conversation.id"] == "session-123"
        assert gen_ai_span["gen_ai.usage.input_tokens"] == 10
        assert gen_ai_span["gen_ai.usage.output_tokens"] == 5
        assert gen_ai_span["gen_ai.usage.total_tokens"] == 15

        input_messages_json = gen_ai_span["gen_ai.input.messages"]
        assert isinstance(input_messages_json, str)
        input_messages = cast("list[GenAiMessage]", json.loads(input_messages_json))
        assert input_messages == [{"role": "user", "content": "hello"}]
        output_messages_json = gen_ai_span["gen_ai.output.messages"]
        assert isinstance(output_messages_json, str)
        output_messages = cast("list[GenAiMessage]", json.loads(output_messages_json))
        assert output_messages == [{"role": "assistant", "content": "hi there"}]

        metadata_json = gen_ai_span["_dd.ml_obs.metadata"]
        assert isinstance(metadata_json, str)
        metadata = cast("GenAiMetadata", json.loads(metadata_json))
        assert metadata["temperature"] == 0.7

    @pytest.mark.parametrize(
        ("target_headers", "target_service_name", "expected_failure"), INVALID_TARGET_METADATA_CASES
    )
    def test_matching_request_metadata_is_not_merged(
        self,
        target_headers: Headers,
        target_service_name: str,
        expected_failure: str,
    ) -> None:
        captured = [
            _synthetic_trace_request(
                headers=target_headers,
                service_name=target_service_name,
                operation_name="chat",
            ),
            _synthetic_trace_request(
                headers={"dd-otlp-source": "llmobs", "dd-ml-app": "test-app"},
                service_name="test-service",
                operation_name="unrelated",
            ),
        ]

        with pytest.raises(AssertionError, match=expected_failure):
            _validated_gen_ai_chat_span(captured)
