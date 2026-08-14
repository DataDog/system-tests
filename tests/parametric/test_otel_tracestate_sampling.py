import base64
import json
import time

import pytest
from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from tests.test_otel_tracestate_sampling import (
    FORWARD_RV,
    FORWARD_TH,
    FORWARD_TRACE_ID,
    SAMPLING_RATE_0_01,
    SAMPLING_RATE_0_1,
    SAMPLING_RATE_0_2,
    SAMPLING_RATE_0_5,
    SAMPLING_RATE_0_99,
    TH_BY_RATE,
    _parse_ot,
    _traceparent,
)
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.spec.tracecontext import get_tracecontext

from .conftest import APMLibrary


def _library_env(rate: float) -> dict[str, str]:
    return {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "datadog,tracecontext",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "tracecontext",
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


def _make_child_headers(test_library: APMLibrary, headers: list[tuple[str, str]]) -> dict[str, str]:
    return test_library.dd_make_child_span_and_get_headers(headers)


def _make_manual_keep_headers(test_library: APMLibrary, headers: list[tuple[str, str]]) -> dict[str, str]:
    with test_library.dd_extract_headers_and_make_child_span("name", headers) as span:
        span.manual_keep()
        return {key.lower(): value for key, value in test_library.dd_inject_headers(span.span_id)}


def _make_root_manual_keep_headers(test_library: APMLibrary) -> dict[str, str]:
    with test_library.dd_start_span("name") as span:
        span.manual_keep()
        return {key.lower(): value for key, value in test_library.dd_inject_headers(span.span_id)}


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


SAMPLE_RATE_VECTORS = [
    pytest.param(_library_env(0.01), 0.01, SAMPLING_RATE_0_01, id="rate-0.01"),
    pytest.param(_library_env(0.1), 0.1, SAMPLING_RATE_0_1, id="rate-0.1"),
    pytest.param(_library_env(0.2), 0.2, SAMPLING_RATE_0_2, id="rate-0.2"),
    pytest.param(_library_env(0.5), 0.5, SAMPLING_RATE_0_5, id="rate-0.5"),
    pytest.param(_library_env(0.99), 0.99, SAMPLING_RATE_0_99, id="rate-0.99"),
]


@features.w3c_headers_injection_and_extraction
@scenarios.parametric
class Test_OtelTracestateSampling:
    @pytest.mark.parametrize(("library_env", "rate", "vectors"), SAMPLE_RATE_VECTORS)
    def test_emits_probability_sampling_vectors(
        self, test_library: APMLibrary, rate: float, vectors: list[tuple[int, str, bool]]
    ) -> None:
        with test_library:
            for trace_id, expected_rv, expected_sampled in vectors:
                headers = test_library.dd_make_child_span_and_get_headers(
                    [
                        ("x-datadog-trace-id", str(trace_id)),
                        ("x-datadog-parent-id", str(trace_id)),
                    ]
                )
                traceparent, tracestate = get_tracecontext(headers)
                ot = _parse_ot(tracestate)

                assert ot == {"rv": expected_rv, "th": TH_BY_RATE[rate]}
                assert (traceparent.trace_flags == "01") is expected_sampled

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_forwards_and_sanitizes_inbound_ot(self, test_library: APMLibrary) -> None:
        inherited = f"dd=s:2;t.dm:-3,ot=rv:{FORWARD_RV};th:{FORWARD_TH};foo:bar,congo=t61rcWkgMzE"
        malformed = "dd=s:1,ot=rv:not-hex;th:not-hex,congo=xyz123"
        th_only = f"ot=th:{FORWARD_TH}"

        with test_library:
            inherited_headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", inherited),
                ]
            )
            malformed_headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", malformed),
                ]
            )
            th_only_headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", th_only),
                ]
            )

        _, inherited_tracestate = get_tracecontext(inherited_headers)
        assert _parse_ot(inherited_tracestate) == {
            "rv": FORWARD_RV,
            "th": FORWARD_TH,
            "foo": "bar",
        }
        assert "s:2" in inherited_tracestate["dd"].split(";")
        assert inherited_tracestate["congo"] == "t61rcWkgMzE"

        _, malformed_tracestate = get_tracecontext(malformed_headers)
        assert "ot" not in malformed_tracestate
        assert "dd" in malformed_tracestate
        assert malformed_tracestate["congo"] == "xyz123"

        _, th_only_tracestate = get_tracecontext(th_only_headers)
        assert _parse_ot(th_only_tracestate) == {"th": FORWARD_TH}

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_forwards_unknown_inbound_ot_subkeys(self, test_library: APMLibrary) -> None:
        inherited = f"ot=rv:{FORWARD_RV};th:{FORWARD_TH};foo:bar"
        unknown_only = "ot=foo:bar"

        with test_library:
            inherited_headers = _make_child_headers(
                test_library,
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", inherited),
                ],
            )
            unknown_only_headers = _make_child_headers(
                test_library,
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", unknown_only),
                ],
            )

        _, inherited_tracestate = get_tracecontext(inherited_headers)
        assert _parse_ot(inherited_tracestate) == {"rv": FORWARD_RV, "th": FORWARD_TH, "foo": "bar"}

        _, unknown_only_tracestate = get_tracecontext(unknown_only_headers)
        assert _parse_ot(unknown_only_tracestate) == {"foo": "bar"}

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_forwards_dropped_inbound_ot(self, test_library: APMLibrary) -> None:
        with test_library:
            headers = _make_child_headers(
                test_library,
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=False)),
                    ("tracestate", f"dd=s:0,ot=rv:{FORWARD_RV};th:{FORWARD_TH}"),
                ],
            )

        traceparent, tracestate = get_tracecontext(headers)
        assert traceparent.trace_flags == "00"
        assert _parse_ot(tracestate) == {"rv": FORWARD_RV, "th": FORWARD_TH}

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_dropped_th_only_does_not_fabricate_rv(self, test_library: APMLibrary) -> None:
        with test_library:
            headers = _make_child_headers(
                test_library,
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=False)),
                    ("tracestate", f"ot=th:{FORWARD_TH}"),
                ],
            )

        traceparent, tracestate = get_tracecontext(headers)
        assert traceparent.trace_flags == "00"
        assert _parse_ot(tracestate) == {"th": FORWARD_TH}

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_force_keep_clears_th(self, test_library: APMLibrary) -> None:
        with test_library:
            no_ot_headers = _make_root_manual_keep_headers(test_library)
            rv_only_headers = _make_manual_keep_headers(
                test_library,
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=False)),
                    ("tracestate", "ot=rv:1234567890abcd"),
                ],
            )
            dropped_headers = _make_manual_keep_headers(
                test_library,
                [
                    ("traceparent", _traceparent(10, sampled=False)),
                    ("tracestate", "ot=rv:65cd67504a538e;th:e6666666666668"),
                ],
            )

        no_ot_traceparent, no_ot_tracestate = get_tracecontext(no_ot_headers)
        assert no_ot_traceparent.trace_flags == "01"
        assert "ot" not in no_ot_tracestate

        rv_only_traceparent, rv_only_tracestate = get_tracecontext(rv_only_headers)
        assert rv_only_traceparent.trace_flags == "01"
        assert _parse_ot(rv_only_tracestate) == {"rv": "1234567890abcd"}

        dropped_traceparent, dropped_tracestate = get_tracecontext(dropped_headers)
        assert dropped_traceparent.trace_flags == "01"
        assert _parse_ot(dropped_tracestate) == {"rv": "65cd67504a538e"}

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_sampled_without_ot_does_not_fabricate_it(self, test_library: APMLibrary) -> None:
        with test_library:
            headers = _make_child_headers(
                test_library,
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", "dd=s:1"),
                ],
            )

        traceparent, tracestate = get_tracecontext(headers)
        assert traceparent.trace_flags == "01"
        assert "ot" not in tracestate

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_malformed_th_preserves_rv(self, test_library: APMLibrary) -> None:
        with test_library:
            headers = _make_child_headers(
                test_library,
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=True)),
                    ("tracestate", "ot=rv:1234567890abcd;th:not-hex-either"),
                ],
            )

        _, tracestate = get_tracecontext(headers)
        assert _parse_ot(tracestate) == {"rv": "1234567890abcd"}

    @pytest.mark.parametrize(
        ("library_env", "trace_id", "expected_th", "expected_rv", "expected_sampled"),
        [
            pytest.param(
                _library_env(0.1),
                0x03A93EE8B1999F00,
                "e6666666666668",
                "e6666666666668",
                True,
                id="rate-0.1-kept",
            ),
            pytest.param(
                _library_env(0.05),
                5401449561355763072,
                "f333333333333",
                "f333333333332f",
                False,
                id="rate-0.05-dropped",
            ),
        ],
    )
    def test_precision_boundary_decisions(
        self,
        test_library: APMLibrary,
        trace_id: int,
        expected_th: str,
        expected_rv: str,
        *,
        expected_sampled: bool,
    ) -> None:
        with test_library:
            headers = _make_child_headers(
                test_library,
                [
                    ("x-datadog-trace-id", str(trace_id)),
                    ("x-datadog-parent-id", str(trace_id)),
                ],
            )

        traceparent, tracestate = get_tracecontext(headers)
        assert _parse_ot(tracestate) == {"rv": expected_rv, "th": expected_th}
        assert (traceparent.trace_flags == "01") is expected_sampled


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
