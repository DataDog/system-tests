"""Shared OpenTelemetry tracestate sampling fixtures."""

# ---------------------------------------------------------------------------
# Expected ot.rv / ot.th values for known trace IDs and known sample rates
#
# DD's sampling decision is h = (trace_id_low64 * 1111111111111111111) mod 2**64, keep if h <= rate * (2**64 - 1)
# (dd-trace-go/ddtrace/tracer/sampler.go:114-122). The OTel-compatible pair is:
#   rv = (~h & (2**64 - 1)) >> 8      (56-bit, 14 hex digits) -- depends only on trace_id, not on rate
#   th = round((1 - rate) * (2**56)) (56-bit, trailing zero nibbles trimmed when formatted) -- depends only on rate
#   These fixtures use the maximum available 14 hexadecimal digits of precision, rather than the 4 digits
#   recommended by the OTel specification: https://opentelemetry.io/docs/specs/otel/trace/tracestate-probability-sampling/
#
# Trace IDs are the ones already used (and verified) in tests/fixtures/sampling_rates.csv, crossed with
# 5 rates. Expected values below were computed with the formula above and cross-checked: at rate 0.5 they
# reproduce the exact same keep/drop decisions as that CSV for all 23 trace IDs.
# ---------------------------------------------------------------------------

TH_BY_RATE: dict[float, str] = {
    0.01: "fd70a3d70a3d7",
    0.1: "e6666666666668",
    0.2: "ccccccccccccd",
    0.5: "8",
    0.99: "028f5c28f5c29",
}

SamplingVector = tuple[int, str, bool]

SAMPLING_RATE_0_01: list[SamplingVector] = [
    # (trace_id, expected_rv_hex, expected_sampled)
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

SAMPLING_RATE_0_1: list[SamplingVector] = [
    # (trace_id, expected_rv_hex, expected_sampled)
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

SAMPLING_RATE_0_2: list[SamplingVector] = [
    # (trace_id, expected_rv_hex, expected_sampled)
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

SAMPLING_RATE_0_5: list[SamplingVector] = [
    # (trace_id, expected_rv_hex, expected_sampled)
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

SAMPLING_RATE_0_99: list[SamplingVector] = [
    # (trace_id, expected_rv_hex, expected_sampled)
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

FORWARD_TRACE_ID = 18444899399302180863
FORWARD_RV = "ef284ace7a91e1"
FORWARD_TH = "e6666666666668"
