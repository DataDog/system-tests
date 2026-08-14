"""Cross-tracer conformance for OpenTelemetry probability sampling on the wire."""

import base64
import json
import time

import pytest
from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from utils import features, scenarios
from utils.dd_constants import SamplingPriority
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.spec.trace import SAMPLING_PRIORITY_KEY, find_trace
from utils.docker_fixtures.spec.tracecontext import Tracestate, get_tracecontext

from .conftest import APMLibrary


# Expected `ot.rv` / `ot.th` values for known trace IDs and sample rates.
#
# The sampling decision is derived from a 64-bit hash of the trace ID. `rv` is
# the corresponding 56-bit value and depends only on the trace ID; `th` is the
# 56-bit threshold and depends only on the configured sample rate.
#
# These fixtures use the maximum 14 hexadecimal digits of precision. Their
# trace IDs are cross-checked against the existing sampling-rate fixtures.
TH_BY_RATE = {
    0.01: "fd70a3d70a3d7",
    0.1: "e6666666666668",
    0.2: "ccccccccccccd",
    0.5: "8",
    0.99: "028f5c28f5c29",
}

SAMPLING_RATE_0_01 = [
    (1, "f0948a54d43b8e", False),
    (10, "65cd67504a538e", False),
    (100, "fa060922e7438e", False),
    (1000, "c43c5b5d08a38e", False),
    (18444899399302180860, "1d6aabcffddf37", False),
    (18444899399302180861, "0dff3624d21ac5", False),
    (18444899399302180862, "fe93c079a65653", True),
    (18444899399302180863, "ef284ace7a91e1", False),
    (18446744073709551615, "0f6b75ab2bc471", False),
    (9223372036854775809, "70948a54d43b8e", False),
    (9223372036854775807, "8f6b75ab2bc471", False),
    (4611686018427387905, "30948a54d43b8e", False),
    (4611686018427387903, "4f6b75ab2bc471", False),
    (646771306295669658, "899fbcfd433be9", False),
    (1882305164521835798, "9d38be3d27241d", False),
    (5198373796167680436, "7188fdce730439", False),
    (6272545487220484606, "bea00261cb73bd", False),
    (8696342848850656916, "ca47c7b1ab2e46", False),
    (10197320802478874805, "d29c6d21f144ee", False),
    (10350218024687037124, "d6dc160c1c68fd", False),
    (12078589664685934330, "3a7d76f3c5a379", False),
    (13794769880582338323, "a6c17470cee7cd", False),
    (14629469446186818297, "295fd564326a5f", False),
    (83, "0028d980cf4f1c", False),
]

SAMPLING_RATE_0_1 = [
    (1, "f0948a54d43b8e", True),
    (10, "65cd67504a538e", False),
    (100, "fa060922e7438e", True),
    (1000, "c43c5b5d08a38e", False),
    (18444899399302180860, "1d6aabcffddf37", False),
    (18444899399302180861, "0dff3624d21ac5", False),
    (18444899399302180862, "fe93c079a65653", True),
    (18444899399302180863, "ef284ace7a91e1", True),
    (18446744073709551615, "0f6b75ab2bc471", False),
    (9223372036854775809, "70948a54d43b8e", False),
    (9223372036854775807, "8f6b75ab2bc471", False),
    (4611686018427387905, "30948a54d43b8e", False),
    (4611686018427387903, "4f6b75ab2bc471", False),
    (646771306295669658, "899fbcfd433be9", False),
    (1882305164521835798, "9d38be3d27241d", False),
    (5198373796167680436, "7188fdce730439", False),
    (6272545487220484606, "bea00261cb73bd", False),
    (8696342848850656916, "ca47c7b1ab2e46", False),
    (10197320802478874805, "d29c6d21f144ee", False),
    (10350218024687037124, "d6dc160c1c68fd", False),
    (12078589664685934330, "3a7d76f3c5a379", False),
    (13794769880582338323, "a6c17470cee7cd", False),
    (14629469446186818297, "295fd564326a5f", False),
    (83, "0028d980cf4f1c", False),
]

SAMPLING_RATE_0_2 = [
    (1, "f0948a54d43b8e", True),
    (10, "65cd67504a538e", False),
    (100, "fa060922e7438e", True),
    (1000, "c43c5b5d08a38e", False),
    (18444899399302180860, "1d6aabcffddf37", False),
    (18444899399302180861, "0dff3624d21ac5", False),
    (18444899399302180862, "fe93c079a65653", True),
    (18444899399302180863, "ef284ace7a91e1", True),
    (18446744073709551615, "0f6b75ab2bc471", False),
    (9223372036854775809, "70948a54d43b8e", False),
    (9223372036854775807, "8f6b75ab2bc471", False),
    (4611686018427387905, "30948a54d43b8e", False),
    (4611686018427387903, "4f6b75ab2bc471", False),
    (646771306295669658, "899fbcfd433be9", False),
    (1882305164521835798, "9d38be3d27241d", False),
    (5198373796167680436, "7188fdce730439", False),
    (6272545487220484606, "bea00261cb73bd", False),
    (8696342848850656916, "ca47c7b1ab2e46", False),
    (10197320802478874805, "d29c6d21f144ee", True),
    (10350218024687037124, "d6dc160c1c68fd", True),
    (12078589664685934330, "3a7d76f3c5a379", False),
    (13794769880582338323, "a6c17470cee7cd", False),
    (14629469446186818297, "295fd564326a5f", False),
    (83, "0028d980cf4f1c", False),
]

SAMPLING_RATE_0_5 = [
    (1, "f0948a54d43b8e", True),
    (10, "65cd67504a538e", False),
    (100, "fa060922e7438e", True),
    (1000, "c43c5b5d08a38e", True),
    (18444899399302180860, "1d6aabcffddf37", False),
    (18444899399302180861, "0dff3624d21ac5", False),
    (18444899399302180862, "fe93c079a65653", True),
    (18444899399302180863, "ef284ace7a91e1", True),
    (18446744073709551615, "0f6b75ab2bc471", False),
    (9223372036854775809, "70948a54d43b8e", False),
    (9223372036854775807, "8f6b75ab2bc471", True),
    (4611686018427387905, "30948a54d43b8e", False),
    (4611686018427387903, "4f6b75ab2bc471", False),
    (646771306295669658, "899fbcfd433be9", True),
    (1882305164521835798, "9d38be3d27241d", True),
    (5198373796167680436, "7188fdce730439", False),
    (6272545487220484606, "bea00261cb73bd", True),
    (8696342848850656916, "ca47c7b1ab2e46", True),
    (10197320802478874805, "d29c6d21f144ee", True),
    (10350218024687037124, "d6dc160c1c68fd", True),
    (12078589664685934330, "3a7d76f3c5a379", False),
    (13794769880582338323, "a6c17470cee7cd", True),
    (14629469446186818297, "295fd564326a5f", False),
    (83, "0028d980cf4f1c", False),
]

SAMPLING_RATE_0_99 = [
    (1, "f0948a54d43b8e", True),
    (10, "65cd67504a538e", True),
    (100, "fa060922e7438e", True),
    (1000, "c43c5b5d08a38e", True),
    (18444899399302180860, "1d6aabcffddf37", True),
    (18444899399302180861, "0dff3624d21ac5", True),
    (18444899399302180862, "fe93c079a65653", True),
    (18444899399302180863, "ef284ace7a91e1", True),
    (18446744073709551615, "0f6b75ab2bc471", True),
    (9223372036854775809, "70948a54d43b8e", True),
    (9223372036854775807, "8f6b75ab2bc471", True),
    (4611686018427387905, "30948a54d43b8e", True),
    (4611686018427387903, "4f6b75ab2bc471", True),
    (646771306295669658, "899fbcfd433be9", True),
    (1882305164521835798, "9d38be3d27241d", True),
    (5198373796167680436, "7188fdce730439", True),
    (6272545487220484606, "bea00261cb73bd", True),
    (8696342848850656916, "ca47c7b1ab2e46", True),
    (10197320802478874805, "d29c6d21f144ee", True),
    (10350218024687037124, "d6dc160c1c68fd", True),
    (12078589664685934330, "3a7d76f3c5a379", True),
    (13794769880582338323, "a6c17470cee7cd", True),
    (14629469446186818297, "295fd564326a5f", True),
    (83, "0028d980cf4f1c", False),
]

# This trace ID and its `rv`/`th` values match the verified OpenTelemetry
# sampling example at rate 0.1.
FORWARD_TRACE_ID = 18444899399302180863
FORWARD_RV = "ef284ace7a91e1"
FORWARD_TH = "e6666666666668"


def _traceparent(trace_id: int, *, sampled: bool) -> str:
    return f"00-{trace_id:032x}-0000000000000001-{'01' if sampled else '00'}"


def _parse_ot(tracestate: Tracestate | str) -> dict[str, str]:
    """Split the `ot` tracestate member into subkeys without assuming their order."""
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
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        rate: float,
        vectors: list[tuple[int, str, bool]],
    ) -> None:
        """A1: A probability decision emits an `ot` member consistent with its sampling priority."""
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

        traces = test_agent.wait_for_num_traces(len(vectors))
        for trace_id, _, expected_sampled in vectors:
            (span,) = find_trace(traces, trace_id)
            sampling_priority = span["metrics"].get(SAMPLING_PRIORITY_KEY)
            assert sampling_priority is not None
            assert (sampling_priority in (SamplingPriority.AUTO_KEEP, SamplingPriority.USER_KEEP)) is expected_sampled

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_forwards_and_sanitizes_inbound_ot(self, test_library: APMLibrary) -> None:
        """A2/A3/A6: Preserve inherited decisions and other vendors while clearing malformed `ot` data."""
        inherited = f"dd=s:2;t.dm:-3,ot=rv:{FORWARD_RV};th:{FORWARD_TH};foo:bar,congo=t61rcWkgMzE"
        # `dd=s:1` is the sampling decision here, so the traceparent flag must agree.
        malformed = "dd=s:1,ot=rv:not-hex;th:not-hex,congo=xyz123"
        # A `th` without an `rv` is a valid default-sampling decision.
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
        # An unrelated vendor member is opaque and must be forwarded byte-for-byte.
        assert inherited_tracestate["congo"] == "t61rcWkgMzE"

        _, malformed_tracestate = get_tracecontext(malformed_headers)
        assert "ot" not in malformed_tracestate
        assert "dd" in malformed_tracestate
        assert malformed_tracestate["congo"] == "xyz123"

        _, th_only_tracestate = get_tracecontext(th_only_headers)
        assert _parse_ot(th_only_tracestate) == {"th": FORWARD_TH}

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_forwards_unknown_inbound_ot_subkeys(self, test_library: APMLibrary) -> None:
        """Unknown `ot` subkeys are forwarded transparently without fabricating a sampling decision."""
        # `ot` currently defines `rv` and `th`, but reserved subkeys must also survive propagation.
        inherited = f"ot=rv:{FORWARD_RV};th:{FORWARD_TH};foo:bar"
        # An unknown-only `ot` member carries no sampling decision.
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
        """A2c: An inherited dropped decision is forwarded unchanged."""
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
        """A2d: A dropped `th`-only decision is forwarded without fabricating an `rv`."""
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
    def test_force_keep_clears_th(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """A4: A manual keep clears `th` while preserving an inherited `rv`."""
        with test_library:
            # Nothing was inherited, so a manual keep must not fabricate an `ot` member.
            no_ot_headers = _make_root_manual_keep_headers(test_library)
            # An inherited `rv` remains meaningful even without an inherited `th` decision.
            rv_only_headers = _make_manual_keep_headers(
                test_library,
                [
                    ("traceparent", _traceparent(FORWARD_TRACE_ID, sampled=False)),
                    ("tracestate", "ot=rv:1234567890abcd"),
                ],
            )
            # Override a complete inherited drop decision, not merely an inherited `rv`.
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

        traces = test_agent.wait_for_num_traces(3)
        for trace in traces:
            (span,) = trace
            assert span["metrics"].get(SAMPLING_PRIORITY_KEY) == SamplingPriority.USER_KEEP

    @pytest.mark.parametrize("library_env", [_library_env(0.1)])
    def test_sampled_without_ot_does_not_fabricate_it(self, test_library: APMLibrary) -> None:
        """A5: A sampled inbound trace without `ot` does not fabricate `rv` or `th`."""
        # A parent-based child with an unknown upstream probability cannot create `th` or `rv`.
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
        """A6: A malformed `th` is removed while a well-formed inherited `rv` is retained."""
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
            # Keep: the 56-bit `rv` is raised to `th` to match the 64-bit decision.
            pytest.param(
                _library_env(0.1),
                0x03A93EE8B1999F00,
                "e6666666666668",
                "e6666666666668",
                True,
                id="rate-0.1-kept",
            ),
            # Drop: the 56-bit `rv` is lowered to `th - 1` to match the 64-bit decision.
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
        """A7: At precision boundaries, the `rv`/`th` pair reproduces the 64-bit decision."""
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
        """B1: A probability decision is carried in the exported OTLP span's `ot` member."""
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
        """B2: An inherited `ot` decision is forwarded unchanged onto the exported OTLP span."""
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
