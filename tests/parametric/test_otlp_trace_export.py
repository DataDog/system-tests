"""Cross-tracer conformance for OTLP trace export tracestate."""

import base64
import json
import time

import pytest
from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.spec.tracecontext import Tracestate

from .conftest import APMLibrary


FORWARD_TRACE_ID = 18444899399302180863
FORWARD_RV = "ef284ace7a91e1"
FORWARD_TH = "e6666666666668"


def _traceparent(trace_id: int, *, sampled: bool) -> str:
    return f"00-{trace_id:032x}-0000000000000001-{'01' if sampled else '00'}"


def _parse_ot(tracestate: Tracestate | str) -> dict[str, str]:
    """Split the ot= list-member into its rv/th sub-keys. Sub-key order isn't guaranteed by spec."""
    if isinstance(tracestate, str):
        tracestate = Tracestate(tracestate)

    if "ot" not in tracestate:
        return {}

    parsed = {}
    for item in tracestate["ot"].split(";"):
        if ":" not in item:
            continue
        key, _, value = item.partition(":")
        parsed[key] = value
    return parsed


def _library_env(rate: float) -> dict[str, str]:
    return {
        "DD_TRACE_RATE_LIMIT": "10000000",
        "DD_TRACE_SAMPLE_RATE": str(rate),
        "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
    }


def _otlp_library_env() -> dict[str, str]:
    return {
        **_library_env(0.1),
        "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "http/json",
        "OTEL_TRACES_EXPORTER": "otlp",
    }


@pytest.fixture
def otlp_library_env(library_env: dict[str, str], test_agent: TestAgentAPI) -> dict[str, str]:
    library_env["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = f"http://{test_agent.container_name}:4318/v1/traces"
    return library_env


def _otlp_trace_requests(test_agent: TestAgentAPI) -> list[dict]:
    return [request for request in test_agent.otlp_requests() if request["url"].endswith("/v1/traces")]


def _wait_for_otlp_trace_requests(test_agent: TestAgentAPI) -> list[dict]:
    for _ in range(80):
        requests = _otlp_trace_requests(test_agent)
        if requests:
            return requests
        time.sleep(0.1)
    raise AssertionError("No OTLP trace export request received")


def _decode_otlp_trace_request(request: dict) -> dict:
    body = base64.b64decode(request["body"])
    headers = {key.lower(): value for key, value in request["headers"].items()}
    if "json" in headers.get("content-type", ""):
        return json.loads(body.decode("utf-8"))
    return MessageToDict(ExportTraceServiceRequest.FromString(body), preserving_proto_field_name=False)


def _otlp_spans(requests: list[dict]) -> list[dict]:
    spans: list[dict] = []
    for request in requests:
        body = _decode_otlp_trace_request(request)
        for resource_span in body.get("resourceSpans", []):
            for scope_span in resource_span.get("scopeSpans", []):
                spans.extend(scope_span.get("spans", []))
    return spans


@features.otel_api
@scenarios.parametric
class Test_OtlpTracestateSampling:
    @pytest.mark.parametrize("library_env", [_otlp_library_env()])
    def test_otlp_carries_probability_sampling_ot(
        self,
        otlp_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        """B1: a probability sampling decision is carried on the exported OTLP span's tracestate as ot=rv:...;th:...

        See APMAPI-2172.
        """
        with test_library as library:
            with library.dd_extract_headers_and_make_child_span(
                "name",
                [
                    ("x-datadog-trace-id", str(FORWARD_TRACE_ID)),
                    ("x-datadog-parent-id", str(FORWARD_TRACE_ID)),
                ],
            ):
                pass
            assert library.dd_flush()

        spans = _otlp_spans(_wait_for_otlp_trace_requests(test_agent))
        assert spans, "No span found in the OTLP trace export"
        ot = _parse_ot(spans[0].get("traceState", ""))
        assert ot.get("rv") == FORWARD_RV
        assert ot.get("th") == FORWARD_TH

    @pytest.mark.parametrize("library_env", [_otlp_library_env()])
    def test_otlp_forwards_inherited_ot(
        self,
        otlp_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        """B2: an inherited ot=rv:...;th:... is forwarded unchanged onto the exported OTLP span's tracestate.

        See APMAPI-2172.
        """
        with test_library as library:
            with library.dd_extract_headers_and_make_child_span(
                "name",
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", f"dd=s:2;t.dm:-3,ot=rv:{FORWARD_RV};th:{FORWARD_TH}"),
                ],
            ):
                pass
            assert library.dd_flush()

        spans = _otlp_spans(_wait_for_otlp_trace_requests(test_agent))
        assert spans, "No span found in the OTLP trace export"
        ot = _parse_ot(spans[0].get("traceState", ""))
        assert ot == {"rv": FORWARD_RV, "th": FORWARD_TH}
