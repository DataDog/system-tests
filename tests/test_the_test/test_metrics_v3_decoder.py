# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Characterization tests for the v3 metrics decoder (``utils/proxy/_decoders/metrics_v3.py``).

These tests pin the exact output of ``decode_metrics_v3`` on hand-encoded payloads that
exercise every branch of the decoder (string dictionaries, tagset inheritance via negative
references, delta-encoded reference columns, plain-uvarint columns, missing optional columns,
and multiple ``MetricData`` blobs in one request). They run with no infrastructure under the
``TEST_THE_TEST`` scenario and act as a refactor guard: the asserted dicts must stay identical
across any change to how the bytes are parsed.
"""

import base64
import json
from pathlib import Path

from utils import scenarios
from utils.proxy._decoders.metrics_v3 import decode_metrics_v3

_FIXTURES = Path(__file__).parent / "metrics_v3_fixtures"


# --- minimal v3 wire encoder (the inverse of the decoder) -----------------------------------


def _uvarint(value: int) -> bytes:
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _zigzag(value: int) -> int:
    return (value << 1) ^ (value >> 63) if value < 0 else value << 1


def _sint64(value: int) -> bytes:
    return _uvarint(_zigzag(value))


def _len_delimited_field(field_number: int, payload: bytes) -> bytes:
    tag = (field_number << 3) | 2  # wire type 2 = length-delimited
    return _uvarint(tag) + _uvarint(len(payload)) + payload


def _string_dict(strings: list[str]) -> bytes:
    out = bytearray()
    for s in strings:
        raw = s.encode("utf-8")
        out += _uvarint(len(raw)) + raw
    return bytes(out)


def _tagsets(entries: list[list[int]]) -> bytes:
    """Each entry is a list of raw (delta-decoded) indexes; negatives reference prior tagsets."""
    out = bytearray()
    for raw_indexes in entries:
        out += _sint64(len(raw_indexes))
        prev = 0
        for idx in raw_indexes:
            out += _sint64(idx - prev)  # delta-encoded within the entry
            prev = idx
    return bytes(out)


def _delta_sint64_column(values: list[int]) -> bytes:
    out = bytearray()
    prev = 0
    for v in values:
        out += _sint64(v - prev)
        prev = v
    return bytes(out)


def _uvarint_column(values: list[int]) -> bytes:
    out = bytearray()
    for v in values:
        out += _uvarint(v)
    return bytes(out)


# Column ids, mirroring the decoder / iterable_series_v3.go.
_COL_DICT_NAME_STR = 1
_COL_DICT_TAGS_STR = 2
_COL_DICT_TAGSETS = 3
_COL_TYPE = 10
_COL_NAME_REF = 11
_COL_TAGS_REF = 12
_COL_INTERVAL = 14
_COL_NUM_POINTS = 15
_PAYLOAD_FIELD_METRIC_DATA = 3


def _metric_data(columns: dict[int, bytes]) -> bytes:
    out = bytearray()
    for col_id, blob in columns.items():
        out += _len_delimited_field(col_id, blob)
    return bytes(out)


def _payload(metric_data_blobs: list[bytes]) -> bytes:
    out = bytearray()
    for blob in metric_data_blobs:
        out += _len_delimited_field(_PAYLOAD_FIELD_METRIC_DATA, blob)
    return bytes(out)


# --- tests ----------------------------------------------------------------------------------


@scenarios.test_the_test
def test_decode_metrics_v3_full_payload():
    """A payload with two MetricData blobs exercising every decoder branch."""

    # First blob: two series, tagset inheritance via a negative reference.
    blob1 = _metric_data(
        {
            _COL_DICT_NAME_STR: _string_dict(["metric.a", "metric.b"]),
            _COL_DICT_TAGS_STR: _string_dict(["env:test", "host:h1", "service:s"]),
            # tagset 1 -> [env:test, host:h1]; tagset 2 inherits tagset 1 (-1) then adds service:s (3)
            _COL_DICT_TAGSETS: _tagsets([[1, 2], [-1, 3]]),
            _COL_TYPE: _uvarint_column([3, 2]),
            _COL_NAME_REF: _delta_sint64_column([1, 2]),
            _COL_TAGS_REF: _delta_sint64_column([1, 2]),
            _COL_INTERVAL: _uvarint_column([10, 10]),
            _COL_NUM_POINTS: _uvarint_column([1, 5]),
        }
    )

    # Second blob: one series with no tags (tagsRef 0) and no interval/numPoints columns.
    blob2 = _metric_data(
        {
            _COL_DICT_NAME_STR: _string_dict(["metric.c"]),
            _COL_TYPE: _uvarint_column([1]),
            _COL_NAME_REF: _delta_sint64_column([1]),
            _COL_TAGS_REF: _delta_sint64_column([0]),
        }
    )

    result = decode_metrics_v3(_payload([blob1, blob2]))

    assert result == {
        "series": [
            {
                "metric": "metric.a",
                "tags": ["env:test", "host:h1"],
                "type": 3,
                "interval": 10,
                "numPoints": 1,
            },
            {
                "metric": "metric.b",
                "tags": ["env:test", "host:h1", "service:s"],
                "type": 2,
                "interval": 10,
                "numPoints": 5,
            },
            {
                "metric": "metric.c",
                "tags": [],
                "type": 1,
            },
        ]
    }


@scenarios.test_the_test
def test_decode_metrics_v3_empty_payload():
    assert decode_metrics_v3(b"") == {}


@scenarios.test_the_test
def test_decode_metrics_v3_metric_data_without_series():
    # A MetricData with only dictionaries and no Type column yields no series.
    blob = _metric_data({_COL_DICT_NAME_STR: _string_dict(["metric.a"])})
    assert decode_metrics_v3(_payload([blob])) == {}


@scenarios.test_the_test
def test_decode_metrics_v3_real_payload_snapshot():
    """Golden test against a real agent payload (286 series) captured from RUNTIME_METRICS_ENABLED.

    ``sample.b64`` is the exact, zstd-decompressed bytes the decoder receives; ``sample_expected.json``
    is the snapshot of the current decoder output. Any change to how the bytes are parsed must keep
    this snapshot byte-for-byte identical.
    """
    raw = base64.b64decode((_FIXTURES / "sample.b64").read_text().strip())
    expected = json.loads((_FIXTURES / "sample_expected.json").read_text())

    assert decode_metrics_v3(raw) == expected
