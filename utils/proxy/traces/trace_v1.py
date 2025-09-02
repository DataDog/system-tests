from enum import IntEnum

import msgpack


class V1TracePayloadKeys(IntEnum):
    container_id = 2
    language_name = 3
    language_version = 4
    tracer_version = 5
    runtime_id = 6
    env = 7
    hostname = 8
    app_version = 9
    attributes = 10
    chunks = 11


class V1ChunkKeys(IntEnum):
    priority = 1
    origin = 2
    attributes = 3
    spans = 4
    dropped_trace = 5
    trace_id = 6
    sampling_mechanism = 7


class V1SpanKeys(IntEnum):
    service = 1
    name_value = 2
    resource = 3
    span_id = 4
    parent_id = 5
    start = 6
    duration = 7
    error = 8
    attributes = 9
    type_value = 10
    span_links = 11
    span_events = 12
    env = 13
    version = 14
    component = 15
    span_kind = 16


class V1SpanLinkKeys(IntEnum):
    trace_id = 1
    span_id = 2
    attributes = 3
    trace_state = 4
    flags = 5


class V1SpanEventKeys(IntEnum):
    time = 1
    name_value = 2
    attributes = 3


class V1AnyValueKeys(IntEnum):
    string = 1
    bool_value = 2
    double = 3
    int_value = 4
    bytes_value = 5
    array = 6
    key_value_list = 7

# Keys that are strings so may arrive as indexes into the strings list
_chunk_key_strings = ["origin"]
_span_key_strings = ["service", "name_value", "resource", "type_value", "env", "version", "component"]

def _uncompress_keys(trace_payload: dict, strings: list[str]) -> dict:
    uncompressed_payload = {}
    for k, v in trace_payload.items():
        if k in V1TracePayloadKeys:
            if k == V1TracePayloadKeys.chunks:
                uncompressed_payload[V1TracePayloadKeys.chunks.name] = _uncompress_chunks(v, strings)
            else:
                uncompressed_payload[V1TracePayloadKeys(k).name] = v
        else:
            raise ValueError(f"Unknown V1TracePayloadKey: {k}")

    return uncompressed_payload

def _process_trace_attributes(trace_payload: dict, strings: list[str]) -> dict:
    # Process attributes in chunks
    for chunk in trace_payload.get("chunks", []):
        if "attributes" in chunk:
            chunk["attributes"] = _attributes_to_dict(chunk["attributes"], strings)
        # Process attributes in spans
        for span in chunk.get("spans", []):
            if "attributes" in span:
                span["attributes"] = _attributes_to_dict(span["attributes"], strings)
    return trace_payload

def _attributes_to_dict(attrs: list, strings: list[str]) -> dict:
    if len(attrs) % 3 != 0:
        raise ValueError(f"Attributes list must be a multiple of 3: {attrs}")
    attrs_dict = {}
    for i in range(0, len(attrs), 3):
        k = attrs[i]
        if isinstance(k, int):
            k = strings[k]
        v_type = attrs[i + 1]
        v = attrs[i + 2]
        if v_type == 1: # Attribute value is a string
            if isinstance(v, int):
                v = strings[v]
        attrs_dict[k] = v
    return attrs_dict

def _uncompress_chunks(chunks: list, strings: list[str]) -> list:
    uncompressed_chunks = []
    for chunk in chunks:
        uncompressed_chunk = {}
        for k, v in chunk.items():
            if k in V1ChunkKeys:
                if k == V1ChunkKeys.spans:
                    if V1ChunkKeys(k).name in _chunk_key_strings and isinstance(v, int):
                        v = strings[v]
                    uncompressed_chunk[V1ChunkKeys.spans.name] = _uncompress_spans(v, strings)
                else:
                    uncompressed_chunk[V1ChunkKeys(k).name] = v
            else:
                raise ValueError(f"Unknown V1ChunkKey: {k}")
        uncompressed_chunks.append(uncompressed_chunk)
    return uncompressed_chunks


def _uncompress_spans(spans: list, strings: list[str]) -> list:
    uncompressed_spans = []
    for span in spans:
        uncompressed_span = {}
        for k, v in span.items():
            if k in V1SpanKeys:
                if V1SpanKeys(k).name in _span_key_strings and isinstance(v, int):
                    v = strings[v]
                uncompressed_span[V1SpanKeys(k).name] = v
            else:
                raise ValueError(f"Unknown V1SpanKey: {k}")
        uncompressed_spans.append(uncompressed_span)
    return uncompressed_spans


def _unstream_strings(content: None | str | dict | list, strings: list[str] | None = None) -> list[str]:
    # TODO: is recursion here a bad idea?
    if strings is None:
        strings = [""]
    if isinstance(content, str):
        strings.append(content)
    elif isinstance(content, dict):
        for v in content.values():
            _unstream_strings(v, strings)
    elif isinstance(content, list):
        for item in content:
            _unstream_strings(item, strings)
    return strings


def _deserialize_trace_id(chunk: dict):
    trace_id = chunk.get("trace_id")
    if isinstance(trace_id, bytes):
        chunk["trace_id"] = "0x" + trace_id.hex().upper()
    else:
        raise TypeError(f"Trace ID is not a bytes: {trace_id}")


def deserialize_v1_trace(content: bytes) -> dict:
    data: dict = msgpack.unpackb(content, unicode_errors="replace", strict_map_key=False)

    strings = _unstream_strings(data)
    data = _uncompress_keys(data, strings)
    data = _process_trace_attributes(data, strings)
    for chunk in data.get("chunks", []):
        _deserialize_trace_id(chunk)
    return data
