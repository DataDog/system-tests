import base64
import contextlib
from enum import IntEnum

import msgpack


class V1TracePayloadKeys(IntEnum):
    strings = 1
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
_span_key_strings = [
    "service",
    "name_value",
    "resource",
    "type_value",
    "env",
    "version",
    "component",
    "serviceRef",
    "typeRef",
    "nameRef",
    "resourceRef",
    "envRef",
    "versionRef",
    "componentRef",
]


def _uncompress_keys(trace_payload: dict, strings: list[str]) -> dict:
    uncompressed_payload = {}
    for k, v in trace_payload.items():
        try:
            enum_key = V1TracePayloadKeys(k)
            if k == V1TracePayloadKeys.chunks:
                uncompressed_payload[V1TracePayloadKeys.chunks.name] = _uncompress_chunks(v, strings)
            else:
                uncompressed_payload[enum_key.name] = v
        except ValueError as e:
            raise ValueError(f"Unknown V1TracePayloadKey: {k}") from e

    return uncompressed_payload


def _uncompress_values(trace_payload: dict, strings: list[str]) -> dict:
    uncompressed_payload = {}
    for k, v in trace_payload.items():
        if k == V1TracePayloadKeys.chunks.name:
            uncompressed_payload[k] = _uncompress_chunks_values(v, strings)
        else:
            uncompressed_payload[k] = v

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


def _uncompress_attributes(attrs: dict[str, dict], strings: list[str]) -> dict:
    attrs_dict = {}
    for k, v in attrs.items():
        k_str = strings[int(k)]
        if "stringValueRef" in v:
            v_str = strings[v["stringValueRef"]]
            attrs_dict[k_str] = v_str
        elif "boolValue" in v:
            attrs_dict[k_str] = v["boolValue"]
        elif "doubleValue" in v:
            attrs_dict[k_str] = v["doubleValue"]
        elif "intValue" in v:
            attrs_dict[k_str] = v["intValue"]
        elif "bytesValue" in v:
            attrs_dict[k_str] = v["bytesValue"]
        elif "arrayValue" in v:
            attrs_dict[k_str] = v["arrayValue"]
        elif "keyValueList" in v:
            attrs_dict[k_str] = v["keyValueList"]
        else:
            raise ValueError(f"Unknown attribute value: {v}")
    return attrs_dict


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
        if v_type == 1:  # Attribute value is a string
            if isinstance(v, int):
                v = strings[v]
        attrs_dict[k] = v
    return attrs_dict


def _uncompress_chunks(chunks: list, strings: list[str]) -> list:
    uncompressed_chunks = []
    for chunk in chunks:
        uncompressed_chunk = {}
        for k, v in chunk.items():
            value = v
            try:
                # Check if k is a valid enum value by trying to create the enum
                enum_key = V1ChunkKeys(k)
                if k == V1ChunkKeys.spans:
                    if enum_key.name in _chunk_key_strings and isinstance(value, int):
                        value = strings[v]
                    uncompressed_chunk[V1ChunkKeys.spans.name] = _uncompress_spans(value, strings)
                else:
                    uncompressed_chunk[enum_key.name] = value
            except ValueError as e:
                raise ValueError(f"Unknown V1ChunkKey: {k}") from e
        uncompressed_chunks.append(uncompressed_chunk)
    return uncompressed_chunks


def _uncompress_chunks_values(chunks: list, strings: list[str]) -> list:
    uncompressed_chunks = []
    for chunk in chunks:
        uncompressed_chunk = {}
        for k, v in chunk.items():
            value = v
            if k == V1ChunkKeys.spans.name:
                if k in _chunk_key_strings and isinstance(value, int):
                    value = strings[v]
                uncompressed_chunk[k] = _uncompress_spans_values(value, strings)
            else:
                uncompressed_chunk[k] = value
        uncompressed_chunks.append(uncompressed_chunk)
    return uncompressed_chunks


def _uncompress_spans_values(spans: list, strings: list[str]) -> list:
    uncompressed_spans = []
    for span in spans:
        uncompressed_span = {}
        for k, v in span.items():
            value = v
            if k in _span_key_strings and isinstance(value, int):
                value = strings[v]
            uncompressed_span[k] = value
        uncompressed_spans.append(uncompressed_span)
    return uncompressed_spans


def _uncompress_spans(spans: list, strings: list[str]) -> list:
    uncompressed_spans = []
    for span in spans:
        uncompressed_span = {}
        for k, v in span.items():
            value = v
            try:
                # Check if k is a valid enum value by trying to create the enum
                enum_key = V1SpanKeys(k)
                if enum_key.name in _span_key_strings and isinstance(value, int):
                    value = strings[v]
                # Handle span_links specially - they need to be uncompressed
                if enum_key == V1SpanKeys.span_links:
                    if value is not None:
                        value = _uncompress_span_links_list(value, strings)
                # Handle span_events specially - they need to be uncompressed
                elif enum_key == V1SpanKeys.span_events:
                    if value is not None:
                        # Debug: Uncompressing span events
                        value = _uncompress_span_events_list(value, strings)
                uncompressed_span[enum_key.name] = value
            except ValueError as e:
                raise ValueError(f"Unknown V1SpanKey: {k}") from e
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


def _deserialize_base64_trace_id(chunk: dict):
    trace_id = chunk.get("traceID")
    if isinstance(trace_id, str):
        try:
            # Decode the base64-encoded trace_id string to bytes
            trace_id_bytes = base64.b64decode(trace_id)
        except Exception as e:
            raise ValueError(f"Failed to decode base64 trace_id: {trace_id!r}") from e
        chunk["traceID"] = "0x" + trace_id_bytes.hex().upper()
    else:
        raise TypeError(f"Trace ID is not a bytes: {trace_id}")


def deserialize_v1_trace(content: bytes) -> dict:
    data: dict = msgpack.unpackb(content, unicode_errors="replace", strict_map_key=False)

    strings = _unstream_strings(data)
    if len(data) == 0:
        return {}

    data = _uncompress_keys(data, strings)
    data = _process_trace_attributes(data, strings)
    for chunk in data.get("chunks", []):
        _deserialize_trace_id(chunk)
    return data


def _uncompress_span_links_list(span_links: list | None, strings: list[str]) -> list | None:
    """Uncompress a list of span links by converting integer keys to string keys."""
    if span_links is None or not isinstance(span_links, list):
        return span_links

    uncompressed_links = []
    for link in span_links:
        if not isinstance(link, dict):
            uncompressed_links.append(link)
            continue
        uncompressed_link = {}
        for k, v in link.items():
            value = v
            try:
                # Check if k is a valid enum value by trying to create the enum
                enum_key = V1SpanLinkKeys(k)
                # Convert integer key to string key name
                uncompressed_link[enum_key.name] = value
            except ValueError:
                # Keep non-enum keys as-is (for backward compatibility)
                uncompressed_link[k] = value

        # Deserialize trace_id if present (handle both bytes and base64-encoded string)
        if "trace_id" in uncompressed_link:
            trace_id = uncompressed_link["trace_id"]
            if isinstance(trace_id, bytes):
                # Convert bytes to hex string (same as chunk trace IDs)
                uncompressed_link["trace_id"] = "0x" + trace_id.hex().upper()
            elif isinstance(trace_id, str):
                try:
                    # Decode the base64-encoded trace_id string to bytes, then to hex
                    trace_id_bytes = base64.b64decode(trace_id)
                    uncompressed_link["trace_id"] = "0x" + trace_id_bytes.hex().upper()
                except Exception:  # noqa: S110
                    # If it's not base64, it might already be in hex format
                    pass

        # Uncompress attributes
        if "attributes" in uncompressed_link:
            attrs = uncompressed_link["attributes"]
            # Check if attributes are in list format (key, type, value triplets)
            if isinstance(attrs, list):
                uncompressed_link["attributes"] = _attributes_to_dict(attrs, strings)
            else:
                with contextlib.suppress(Exception):
                    # If attributes can't be uncompressed, keep as-is
                    uncompressed_link["attributes"] = _uncompress_attributes(attrs, strings)

        # Resolve tracestateRef to tracestate (if present as integer key)
        if "trace_state" in uncompressed_link:
            trace_state = uncompressed_link["trace_state"]
            # If trace_state is an integer, it might be a reference to strings array
            if isinstance(trace_state, int) and trace_state < len(strings):
                uncompressed_link["tracestate"] = strings[trace_state]

        uncompressed_links.append(uncompressed_link)
    return uncompressed_links


def _uncompress_span_events_list(span_events: list | None, strings: list[str]) -> list | None:
    """Uncompress a list of span events by converting integer keys to string keys."""
    if span_events is None or not isinstance(span_events, list):
        return span_events

    uncompressed_events = []
    for event in span_events:
        if not isinstance(event, dict):
            uncompressed_events.append(event)
            continue
        uncompressed_event = {}
        for k, v in event.items():
            value = v
            try:
                # Check if k is a valid enum value by trying to create the enum
                enum_key = V1SpanEventKeys(k)
                # Convert integer key to string key name
                # Map time -> time_unix_nano and name_value -> name for consistency
                if enum_key == V1SpanEventKeys.time:
                    uncompressed_event["time_unix_nano"] = value
                elif enum_key == V1SpanEventKeys.name_value:
                    # Resolve name_value from strings array if it's an integer
                    if isinstance(value, int) and value < len(strings):
                        uncompressed_event["name"] = strings[value]
                    else:
                        uncompressed_event["name"] = value
                else:
                    uncompressed_event[enum_key.name] = value
            except ValueError:
                # Keep non-enum keys as-is (for backward compatibility)
                uncompressed_event[k] = value

        # Uncompress attributes
        if "attributes" in uncompressed_event:
            attrs = uncompressed_event["attributes"]
            # Check if attributes are in list format (key, type, value triplets)
            if isinstance(attrs, list):
                uncompressed_event["attributes"] = _attributes_to_dict(attrs, strings)
            else:
                with contextlib.suppress(Exception):
                    # If attributes can't be uncompressed, keep as-is
                    uncompressed_event["attributes"] = _uncompress_attributes(attrs, strings)

        uncompressed_events.append(uncompressed_event)
    return uncompressed_events


def _uncompress_span_link(link: dict, strings: list[str]) -> None:
    """Uncompress a span link by deserializing traceID, attributes, and tracestate.
    This function is used for agent interface where links are already partially processed.
    """
    # Convert integer keys to string keys if needed
    if any(isinstance(k, int) for k in link):
        uncompressed_link = {}
        for k, v in link.items():
            try:
                enum_key = V1SpanLinkKeys(k)
                uncompressed_link[enum_key.name] = v
            except ValueError:
                # Keep non-enum keys as-is
                uncompressed_link[k] = v
        link.clear()
        link.update(uncompressed_link)

    # Deserialize traceID (handle both bytes and base64-encoded string)
    if "trace_id" in link:
        trace_id = link["trace_id"]
        if isinstance(trace_id, bytes):
            # Convert bytes to hex string (same as chunk trace IDs)
            link["trace_id"] = "0x" + trace_id.hex().upper()
        elif isinstance(trace_id, str) and not trace_id.startswith("0x"):
            try:
                trace_id_bytes = base64.b64decode(trace_id)
                link["trace_id"] = "0x" + trace_id_bytes.hex().upper()
            except Exception:  # noqa: S110
                pass
    elif "traceID" in link:
        _deserialize_base64_trace_id(link)

    # Uncompress attributes
    if "attributes" in link:
        link["attributes"] = _uncompress_attributes(link["attributes"], strings)

    # Resolve tracestateRef to tracestate
    if "tracestateRef" in link:
        tracestate_ref = link.pop("tracestateRef")
        if isinstance(tracestate_ref, int) and tracestate_ref < len(strings):
            link["tracestate"] = strings[tracestate_ref]
    elif "trace_state" in link:
        trace_state = link["trace_state"]
        if isinstance(trace_state, int) and trace_state < len(strings):
            link["tracestate"] = strings[trace_state]


def _uncompress_span_event(event: dict, strings: list[str]) -> None:
    """Uncompress a span event by deserializing time, name, and attributes.
    This function is used for agent interface where events are already partially processed.
    """
    # Convert integer keys to string keys if needed
    if any(isinstance(k, int) for k in event):
        uncompressed_event = {}
        for k, v in event.items():
            try:
                enum_key = V1SpanEventKeys(k)
                # Map time -> time_unix_nano and name_value -> name for consistency
                if enum_key == V1SpanEventKeys.time:
                    uncompressed_event["time_unix_nano"] = v
                elif enum_key == V1SpanEventKeys.name_value:
                    # Resolve name_value from strings array if it's an integer
                    if isinstance(v, int) and v < len(strings):
                        uncompressed_event["name"] = strings[v]
                    else:
                        uncompressed_event["name"] = v
                else:
                    uncompressed_event[enum_key.name] = v
            except ValueError:
                # Keep non-enum keys as-is
                uncompressed_event[k] = v
        event.clear()
        event.update(uncompressed_event)
    else:
        # Handle name_value -> name mapping even if keys are already strings
        if "name_value" in event:
            name_value = event.pop("name_value")
            if isinstance(name_value, int) and name_value < len(strings):
                event["name"] = strings[name_value]
            else:
                event["name"] = name_value
        # Handle time -> time_unix_nano mapping
        if "time" in event and "time_unix_nano" not in event:
            event["time_unix_nano"] = event.pop("time")

    # Uncompress attributes
    if "attributes" in event:
        event["attributes"] = _uncompress_attributes(event["attributes"], strings)


def _uncompress_agent_v1_trace(data: dict, interface: str):
    if interface != "agent":
        return None
    if "idxTracerPayloads" not in data:
        return None
    for idx, idx_tracer_payload in enumerate(data.get("idxTracerPayloads", [])):
        strings = idx_tracer_payload.get("strings", [])
        data["idxTracerPayloads"][idx] = _uncompress_values(idx_tracer_payload, strings)
        data["idxTracerPayloads"][idx]["attributes"] = _uncompress_attributes(
            data["idxTracerPayloads"][idx].get("attributes", {}), strings
        )
        for chunk in data["idxTracerPayloads"][idx].get("chunks", []):
            _deserialize_base64_trace_id(chunk)
            chunk["attributes"] = _uncompress_attributes(chunk.get("attributes", {}), strings)
            for span in chunk.get("spans", []):
                span["attributes"] = _uncompress_attributes(span.get("attributes", {}), strings)
                # Uncompress span links
                for link in span.get("links", []):
                    _uncompress_span_link(link, strings)
                # Uncompress span events (handle both camelCase and snake_case field names)
                span_events = span.get("spanEvents") or span.get("span_events")
                if span_events:
                    for event in span_events:
                        _uncompress_span_event(event, strings)
    return data
