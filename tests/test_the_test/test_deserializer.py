from utils import scenarios
from utils.proxy._deserializer import deserialize_http_message
import msgpack


@scenarios.test_the_test
def test_deserialize_http_message():
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

    result = deserialize_http_message(
        path="/v1.0/traces",
        message={
            "status_code": 200,
            "headers": [("content-type", "application/msgpack")],
        },
        content=content,
        interface="library",
        key="response",
        export_content_files_to="",
    )
    assert result == {
        "container_id": "hello",
        "chunks": [
            {
                "spans": [
                    {
                        "service": "my-service",
                        "name_value": "span-name",
                        "resource": 1,
                        "span_id": 1234,
                        "parent_id": 5555,
                        "component": "my-component",
                        "span_kind": 1,
                        "version": "my-version",
                        "env": "some-env",
                        "start": 987,
                        "duration": 150,
                        "error": True,
                        "attributes": ["foo", 1, "bar", "fooNum", 3, 3.14],
                        "type_value": "span-type",
                    }
                ],
                "priority": 1,
                "origin": "rum",
                "attributes": ["some-global", 1, "cool-value"],
                "trace_id": bytes(
                    [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x55, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x21, 0xE3]
                ),
                "sampling_mechanism": 4,
            }
        ],
    }
