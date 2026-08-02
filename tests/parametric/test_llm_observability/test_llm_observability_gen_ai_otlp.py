import base64
import json
import time

import pytest

from utils import scenarios, features
from utils.docker_fixtures import TestAgentAPI
from ..conftest import APMLibrary  # noqa: TID252
from utils.docker_fixtures.spec.llm_observability import (
    LlmObsSpanRequest,
    LlmObsAnnotationRequest,
)


@pytest.fixture
def llmobs_ml_app() -> str:
    return "test-app"


@pytest.fixture
def llmobs_gen_ai_otlp_library_env(library_env: dict, test_agent: TestAgentAPI) -> dict:
    library_env["OTEL_TRACES_EXPORTER"] = "otlp"
    # The test agent must capture JSON-decodable OTLP payloads.
    library_env["OTEL_EXPORTER_OTLP_TRACES_PROTOCOL"] = "http/json"
    library_env["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = f"http://{test_agent.container_name}:4318/v1/traces"
    library_env["OTEL_EXPORTER_OTLP_TRACES_HEADERS"] = "dd-otlp-source=llmobs,dd-ml-app=test-app"
    library_env["DD_API_KEY"] = "<not-a-real-key>"
    return library_env


def _attr_value(item: dict):
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


def _otlp_trace_bodies(test_agent: TestAgentAPI) -> list[tuple[dict, dict]]:
    out: list[tuple[dict, dict]] = []
    for r in test_agent.otlp_requests():
        if not r["url"].endswith("/v1/traces"):
            continue
        headers = {h.lower(): v for h, v in r["headers"].items()}
        body = json.loads(base64.b64decode(r["body"]).decode("utf-8"))
        out.append((headers, body))
    return out


def _wait_for_otlp_trace_spans(test_agent: TestAgentAPI, *, deadline_s: float = 20.0) -> list[tuple[dict, dict]]:
    deadline = time.monotonic() + deadline_s
    captured: list[tuple[dict, dict]] = []
    while time.monotonic() < deadline:
        captured = _otlp_trace_bodies(test_agent)
        for _headers, body in captured:
            for rs in body.get("resourceSpans", []):
                for ss in rs.get("scopeSpans", []):
                    if ss.get("spans"):
                        return captured
        time.sleep(0.2)
    raise AssertionError("No OTLP /v1/traces spans captured before deadline")


@features.llm_observability_sdk_enablement
@scenarios.parametric
class Test_GenAI_OTLP:
    """Assert the emitted gen_ai OTLP schema without backend read-back."""

    def test_llm_span_gen_ai_attributes(
        self,
        llmobs_gen_ai_otlp_library_env: dict,  # noqa: ARG002  (mutates library_env before test_library builds)
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
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

        gen_ai_span: dict | None = None
        resource_attrs: dict = {}
        headers_seen: dict = {}
        for headers, body in captured:
            headers_seen.update(headers)
            for rs in body.get("resourceSpans", []):
                for kv in rs.get("resource", {}).get("attributes", []):
                    resource_attrs[kv["key"]] = _attr_value(kv)
                for ss in rs.get("scopeSpans", []):
                    for span in ss.get("spans", []):
                        attrs = {kv["key"]: _attr_value(kv) for kv in span.get("attributes", [])}
                        if attrs.get("gen_ai.operation.name") == "chat":
                            gen_ai_span = attrs

        assert gen_ai_span is not None, "No captured span with gen_ai.operation.name=chat"

        assert gen_ai_span["gen_ai.operation.name"] == "chat"
        assert gen_ai_span["gen_ai.request.model"] == "gpt-4o"
        assert gen_ai_span["gen_ai.provider.name"] == "openai"
        assert gen_ai_span["gen_ai.conversation.id"] == "session-123"
        assert gen_ai_span["gen_ai.usage.input_tokens"] == 10
        assert gen_ai_span["gen_ai.usage.output_tokens"] == 5
        assert gen_ai_span["gen_ai.usage.total_tokens"] == 15

        input_messages = json.loads(gen_ai_span["gen_ai.input.messages"])
        assert input_messages == [{"role": "user", "content": "hello"}]
        output_messages = json.loads(gen_ai_span["gen_ai.output.messages"])
        assert output_messages == [{"role": "assistant", "content": "hi there"}]

        metadata = json.loads(gen_ai_span["_dd.ml_obs.metadata"])
        assert metadata["temperature"] == 0.7

        assert headers_seen.get("dd-otlp-source") == "llmobs"
        assert headers_seen.get("dd-ml-app") == "test-app"

        assert resource_attrs.get("service.name") == "test-service"
