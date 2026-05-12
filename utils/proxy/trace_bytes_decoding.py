# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Shared decoding for trace payload bytes (v0 msgpack meta_struct vs ASCII, v1 bytes_value attributes)."""

import msgpack


def unpack_trace_bytes_msgpack(payload: bytes) -> object:
    """Unpack bytes as MessagePack (same options as trace deserialization elsewhere)."""
    return msgpack.unpackb(payload, unicode_errors="replace", strict_map_key=False)


def decode_trace_bytes_ascii(payload: bytes) -> str:
    """Decode bytes as ASCII (non-meta_struct branch of v0 trace byte handling)."""
    return payload.decode("ascii")


def decode_v1_bytes_value_attribute(payload: bytes) -> object:
    """v1 attribute ``bytes_value``: try MessagePack like ``meta_struct``; else ASCII like other v0 bytes."""
    try:
        return unpack_trace_bytes_msgpack(payload)
    except BaseException:
        try:
            return decode_trace_bytes_ascii(payload)
        except UnicodeDecodeError as e:
            raise ValueError("Error decoding v1 bytes attribute") from e
