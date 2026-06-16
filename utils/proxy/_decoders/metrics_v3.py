# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Decoder for the agent ``/api/intake/metrics/v3/series`` payload.

The v3 metrics intake uses a columnar, dictionary-encoded format that is very different from the
v2 ``datadog.agentpayload.MetricPayload``. The official proto definition lives in the datadog-agent
repo at ``pkg/proto/datadog/dogstatsdhttp/payload.proto`` and the serializer that produces the wire
bytes is ``pkg/serializer/internal/metrics/iterable_series_v3.go``; a cherry-picked copy is checked
in as ``metrics_v3.proto`` (compiled to ``metrics_v3.descriptor`` by ``update_protobuf.sh``).

Wire layout (after the proxy has fully decompressed the concatenated zstd frames):

    Payload {
      reserved 1;
      Metadata metadata = 2;
      repeated MetricData metricData = 3;   // all series data lives here
    }

``MetricData`` is encoded as a set of "columns". Each column is a distinct protobuf field whose
number matches the column id. Protobuf parses the envelope and the packed scalar columns for us, but
three things are encoded *on top* of plain protobuf and have to be undone by hand here:

* the ``dict*Str`` columns are single ``bytes`` blobs holding length-prefixed strings;
* the reference columns (``nameRefs``, ``tagsetRefs``) are delta-encoded;
* ``dictTagsets`` is a self-framed list (a count followed by that many delta-encoded indexes).

This decoder reconstructs a payload shaped like the v2 output, i.e.
``{"series": [{"metric": <name>, "tags": [<tag>, ...], "type": <int>, ...}, ...]}`` so that
``utils/interfaces/_agent.py::get_metrics`` keeps working unchanged.
"""

from __future__ import annotations

from typing import Any

from .protobuf_schemas import MetricsV3Payload


def _read_uvarint(buf: bytes, pos: int) -> tuple[int, int]:
    """Read a base-128 varint from ``buf`` starting at ``pos``. Returns (value, new_pos)."""
    result = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise ValueError("truncated varint")
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            break
        shift += 7
    return result, pos


def _decode_string_dict(blob: bytes) -> list[str]:
    """Decode a string dictionary column: repeated (varint length, raw bytes).

    Returns a list where list[0] is the dict entry referenced by index 1 (dict indexes are
    1-based; index 0 means "empty / no value").
    """
    strings: list[str] = []
    pos = 0
    while pos < len(blob):
        length, pos = _read_uvarint(blob, pos)
        value = blob[pos : pos + length]
        pos += length
        strings.append(value.decode("utf-8", errors="replace"))
    return strings


def _decode_tagsets(values: list[int]) -> list[list[int]]:
    """Decode the (protobuf-decoded) DictTagsets column into a list of tag-string-index lists.

    ``values`` is the flat list of sint64s protobuf yields for the packed ``dictTagsets`` field.
    It is self-framed: each entry is a ``count`` followed by ``count`` delta-encoded indexes.
    A negative index ``-prefixID`` references a previously built tagset (its tags are inherited);
    positive indexes are 1-based references into the DictTagsStr dict.

    Returns a list where entry ``i`` (0-based) corresponds to tagset id ``i + 1``.
    """
    tagsets: list[list[int]] = []
    pos = 0
    total = len(values)
    while pos < total:
        count = values[pos]
        pos += 1

        raw_indexes: list[int] = []
        prev = 0
        for _ in range(count):
            prev += values[pos]  # entries are delta-encoded across the whole tagset
            pos += 1
            raw_indexes.append(prev)

        resolved: list[int] = []
        for idx in raw_indexes:
            if idx < 0:
                # reference to another tagset (1-based id is -idx)
                prefix_id = -idx
                if 1 <= prefix_id <= len(tagsets):
                    resolved.extend(tagsets[prefix_id - 1])
            elif idx > 0:
                resolved.append(idx)
        tagsets.append(resolved)
    return tagsets


def _accumulate_deltas(values: list[int]) -> list[int]:
    """Turn a delta-encoded reference column into absolute values (running sum)."""
    absolute: list[int] = []
    prev = 0
    for delta in values:
        prev += delta
        absolute.append(prev)
    return absolute


def decode_metrics_v3(content: bytes) -> dict:
    """Decode a fully-decompressed v3 series payload into a v2-like dict.

    The returned dict has a ``series`` list whose entries expose at least ``metric`` and
    ``tags`` (and ``type``/``interval`` when present), matching what the v2 ``MetricPayload``
    deserialization produced and what ``interfaces.agent.get_metrics`` consumes.
    """
    # The message is built dynamically from the descriptor, so its fields are not statically
    # typed; treat it as Any to access the generated column attributes.
    payload: Any = MetricsV3Payload.FromString(content)

    # A request may carry several MetricData messages (one per internal payload split).
    series: list[dict] = []
    for metric_data in payload.metricData:
        series.extend(_decode_metric_data(metric_data))

    if not series:
        return {}

    return {"series": series}


def _decode_metric_data(metric_data: Any) -> list[dict]:  # noqa: ANN401 (dynamic protobuf message)
    name_dict = _decode_string_dict(metric_data.dictNameStr)
    tag_dict = _decode_string_dict(metric_data.dictTagStr)
    tagsets = _decode_tagsets(list(metric_data.dictTagsets))

    name_refs = _accumulate_deltas(metric_data.nameRefs)
    tags_refs = _accumulate_deltas(metric_data.tagsetRefs)
    types = list(metric_data.types)
    intervals = list(metric_data.intervals)
    num_points = list(metric_data.numPoints)

    # The Type column has exactly one entry per series, so it defines the series count.
    series_count = len(types) or len(name_refs)

    series: list[dict] = []
    for i in range(series_count):
        name_idx = name_refs[i] if i < len(name_refs) else 0
        metric_name = name_dict[name_idx - 1] if 1 <= name_idx <= len(name_dict) else ""

        tags: list[str] = []
        tags_idx = tags_refs[i] if i < len(tags_refs) else 0
        if 1 <= tags_idx <= len(tagsets):
            for str_idx in tagsets[tags_idx - 1]:
                if 1 <= str_idx <= len(tag_dict):
                    tags.append(tag_dict[str_idx - 1])

        entry: dict = {"metric": metric_name, "tags": tags}
        if i < len(types):
            entry["type"] = types[i]
        if i < len(intervals):
            entry["interval"] = intervals[i]
        if i < len(num_points):
            entry["numPoints"] = num_points[i]

        series.append(entry)

    return series
