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
