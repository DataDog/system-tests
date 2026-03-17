from utils import scenarios
from utils.proxy.traces.trace_v1 import (
    _uncompress_array,
    decode_appsec_s_value,
    deserialize_v1_trace,
    _uncompress_agent_v1_trace,
)
import base64
import msgpack
import pytest


@scenarios.test_the_test
def test_deserialize_http_message():
    content = msgpack.packb(
        {
            2: "hello",
            11: [
                {
                    1: 1,
                    2: "rum",
                    3: ["some-global", 1, "cool-value", 1, 1, 2],
                    4: [
                        {
                            1: "my-service",
                            2: "span-name",
                            3: 1,
                            4: 1234,
                            5: 5555,
                            6: 987,
                            7: 150,
                            8: True,
                            9: ["foo", 1, "bar", "fooNum", 3, 3.14],
                            10: "span-type",
                            13: "some-env",
                            14: "my-version",
                            15: "my-component",
                            16: 1,
                        }
                    ],
                    6: bytes(
                        [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x55, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x21, 0xE3]
                    ),
                    7: 4,
                }
            ],
        }
    )

    result = deserialize_v1_trace(content=content)

    assert result == {
        "container_id": "hello",
        "chunks": [
            {
                "spans": [
                    {
                        "service": "my-service",
                        "name": "span-name",
                        "resource": "hello",
                        "span_id": 1234,
                        "parent_id": 5555,
                        "component": "my-component",
                        "span_kind": 1,
                        "version": "my-version",
                        "env": "some-env",
                        "start": 987,
                        "duration": 150,
                        "error": True,
                        "attributes": {"foo": "bar", "fooNum": 3.14},
                        "type": "span-type",
                    }
                ],
                "priority": 1,
                "origin": "rum",
                "attributes": {"some-global": "cool-value", "hello": "rum"},
                "trace_id": "0x000000000000005500000000000021E3",
                "sampling_mechanism": 4,
            }
        ],
    }


@scenarios.test_the_test
def test_uncompress_agent_v1_trace_with_span_links():
    """Test that span links traceID is properly deserialized from base64 in idxTracerPayloads."""
    # Create a 16-byte trace ID and encode it as base64 (mimics what protobuf returns)
    trace_id_bytes = bytes(
        [0x12, 0x34, 0x56, 0x78, 0x90, 0x12, 0x34, 0x56, 0x78, 0x90, 0x12, 0x34, 0x56, 0x78, 0x90, 0x12]
    )
    trace_id_base64 = base64.b64encode(trace_id_bytes).decode("utf-8")

    # Chunk traceID also needs to be base64 encoded
    chunk_trace_id_bytes = bytes(
        [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x55, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x21, 0xE3]
    )
    chunk_trace_id_base64 = base64.b64encode(chunk_trace_id_bytes).decode("utf-8")

    # Simulated data structure as returned by protobuf MessageToDict
    data = {
        "idxTracerPayloads": [
            {
                "strings": ["", "my-service", "span-name", "web", "link-key", "link-value", "tracestate-value"],
                "attributes": {},
                "chunks": [
                    {
                        "traceID": chunk_trace_id_base64,
                        "spans": [
                            {
                                "service": "my-service",
                                "name_value": "span-name",
                                "typeRef": "web",
                                "attributes": {
                                    "4": {"stringValueRef": 5}  # "link-key": "link-value"
                                },
                                "links": [
                                    {
                                        "traceID": trace_id_base64,
                                        "spanID": "987654321",
                                        "attributes": {
                                            "4": {"stringValueRef": 5}  # "link-key": "link-value"
                                        },
                                        "tracestateRef": 6,
                                        "flags": 2147483649,
                                    }
                                ],
                            }
                        ],
                        "attributes": {},
                    }
                ],
            }
        ]
    }

    result = _uncompress_agent_v1_trace(data, "agent")

    # Verify chunk traceID is deserialized
    assert result["idxTracerPayloads"][0]["chunks"][0]["traceID"] == "0x000000000000005500000000000021E3"

    # Verify span link traceID is deserialized from base64 to hex
    span_link = result["idxTracerPayloads"][0]["chunks"][0]["spans"][0]["links"][0]
    assert span_link["traceID"] == "0x12345678901234567890123456789012"

    # Verify span link attributes are uncompressed
    assert span_link["attributes"] == {"link-key": "link-value"}

    # Verify span link tracestate is resolved from string reference
    assert span_link["tracestate"] == "tracestate-value"
    assert "tracestateRef" not in span_link


@scenarios.test_the_test
def test_uncompress_array_direct():
    """Test _uncompress_array with (type, value) pairs: string ref, double, bool."""
    strings = ["", "first", "second"]
    # Array: string at index 1, double 2.5, bool True
    array = [1, 1, 3, 2.5, 2, True]
    result = _uncompress_array(array, strings)
    assert result == ["first", 2.5, True]


@scenarios.test_the_test
def test_deserialize_v1_trace_span_attributes_array():
    """Test that span attributes with array type (V1AnyValueKeys.array) are uncompressed."""
    # Build payload so that _unstream_strings yields strings = ["", "x", "s", "n", "tag"]
    # Array value [1, 1, 3, 2.5] = string at index 1 ("x"), double 2.5
    content = msgpack.packb(
        {
            2: "x",
            11: [
                {
                    1: 1,
                    4: [
                        {
                            1: "s",
                            2: "n",
                            9: ["tag", 6, [1, 1, 3, 2.5]],
                        }
                    ],
                    6: bytes(
                        [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x55, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x21, 0xE3]
                    ),
                    7: 0,
                }
            ],
        }
    )
    result = deserialize_v1_trace(content)
    span = result["chunks"][0]["spans"][0]
    assert "tag" in span["attributes"]
    assert span["attributes"]["tag"] == ["x", 2.5]


@scenarios.test_the_test
def test_deserialize_v1_trace_appsec_s_base64_gzip():
    """Test that _dd.appsec.s.* attributes with base64-gzip-encoded JSON are decoded."""
    # Value is base64(gzip(json)); decoded content is [{"code":[[[8]],{"len":1}]}]
    content = msgpack.packb(
        {
            2: "cid",
            11: [
                {
                    1: 1,
                    4: [
                        {
                            1: "svc",
                            2: "span",
                            9: [
                                "_dd.appsec.s.req.query",
                                1,
                                "H4sIAAAAAAAAA4uuVkrOT0lVsoqOjraIjdWpVspJzVOyMqyNrY0FAEi0gSwcAAAA",
                            ],
                        }
                    ],
                    6: bytes(
                        [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x55, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x21, 0xE3]
                    ),
                    7: 0,
                }
            ],
        }
    )
    result = deserialize_v1_trace(content)
    span = result["chunks"][0]["spans"][0]
    assert "_dd.appsec.s.req.query" in span["attributes"]
    assert span["attributes"]["_dd.appsec.s.req.query"] == [{"code": [[[8]], {"len": 1}]}]


@scenarios.test_the_test
def test_decode_appsec_s_value_json_array():
    """Test that _dd.appsec.s.* values starting with '[' are parsed as JSON only."""
    assert decode_appsec_s_value("[1,2,3]") == [1, 2, 3]


@scenarios.test_the_test
def test_decode_appsec_s_value_invalid_raises():
    """Test that invalid base64/gzip/json raises ValueError."""
    with pytest.raises(ValueError, match="Invalid base64"):
        decode_appsec_s_value("not-valid-base64!!!")
    with pytest.raises(ValueError, match="Invalid gzip"):
        decode_appsec_s_value(base64.b64encode(b"not gzip").decode())
    with pytest.raises(ValueError, match="Invalid JSON"):
        decode_appsec_s_value("[1,2,invalid")  # starts with [ so treated as JSON


@scenarios.test_the_test
def test_decode_appsec_s_value_accepts_bytes():
    """Test that _dd.appsec.s.* values arriving as bytes (e.g. MessagePack bin) are decoded.

    In v0.4/v0.5 paths _deserialized_nested_json_from_trace_payloads runs before
    _convert_bytes_values, so meta values can still be bytes; decode_appsec_s_value
    must accept bytes to avoid TypeError from str-only operations.
    """
    # JSON array as bytes
    assert decode_appsec_s_value(b"[1,2,3]") == [1, 2, 3]
    # Base64-gzip as bytes (same payload as test_deserialize_v1_trace_appsec_s_base64_gzip)
    b64_gzip = b"H4sIAAAAAAAAA4uuVkrOT0lVsoqOjraIjdWpVspJzVOyMqyNrY0FAEi0gSwcAAAA"
    assert decode_appsec_s_value(b64_gzip) == [{"code": [[[8]], {"len": 1}]}]
    # Invalid UTF-8 bytes raise ValueError
    with pytest.raises(ValueError, match="Invalid UTF-8"):
        decode_appsec_s_value(b"\xff\xfe")
