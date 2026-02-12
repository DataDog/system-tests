from utils import scenarios
from utils.proxy.traces.trace_v1 import deserialize_v1_trace, _uncompress_agent_v1_trace
import msgpack
import base64


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
                        "name_value": "span-name",
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
                        "type_value": "span-type",
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
def test_deserialize_v1_trace_with_span_links():
    """Test that span links are properly deserialized in v1 trace format (library interface)."""
    # Create a 16-byte trace ID for the span link
    link_trace_id_bytes = bytes(
        [0x12, 0x34, 0x56, 0x78, 0x90, 0x12, 0x34, 0x56, 0x78, 0x90, 0x12, 0x34, 0x56, 0x78, 0x90, 0x12]
    )

    # Include tracestate string in content so it gets added to strings array
    # Strings array: [""] (index 0), then strings are added as encountered
    # We'll include "tracestate-value" in the span attributes so it's in the strings array
    content = msgpack.packb(
        {
            2: "hello",
            11: [
                {
                    1: 1,
                    2: "rum",
                    3: ["some-global", 1, "cool-value"],
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
                            9: ["foo", 1, "bar", "tracestate-ref", 1, "tracestate-value"],  # Include tracestate string
                            10: "span-type",
                            # Span links: key 11
                            # Span link keys: 1=trace_id, 2=span_id, 3=attributes, 4=trace_state, 5=flags
                            11: [
                                {
                                    1: link_trace_id_bytes,  # trace_id as bytes
                                    2: 987654321,  # span_id
                                    3: ["link-key", 1, "link-value"],  # attributes [key, type, value]
                                    4: 7,  # trace_state as string reference (index into strings array, "tracestate-value")
                                    5: 2147483649,  # flags
                                }
                            ],
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

    # Verify span links are present and properly deserialized
    span = result["chunks"][0]["spans"][0]
    assert "span_links" in span
    assert len(span["span_links"]) == 1

    span_link = span["span_links"][0]

    # Verify trace_id is deserialized from bytes to hex string (same as chunk trace IDs)
    assert "trace_id" in span_link
    assert span_link["trace_id"] == "0x12345678901234567890123456789012"
    assert isinstance(span_link["trace_id"], str)

    # Verify span_id is preserved
    assert span_link["span_id"] == 987654321

    # Verify attributes are uncompressed
    assert span_link["attributes"] == {"link-key": "link-value"}

    # Verify trace_state is resolved from string reference to tracestate
    # The trace_state index should resolve to "tracestate-value" from the strings array
    # The code adds "tracestate" field when trace_state is a valid string reference
    assert "tracestate" in span_link
    assert span_link["tracestate"] == "tracestate-value"

    # Verify flags are preserved
    assert span_link["flags"] == 2147483649
