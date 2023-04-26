# Util functions to validate JSON trace data from OTel system tests

import json


def validate_trace(traces: list, use_128_bits_trace_id: bool):
    server_span = None
    message_span = None
    for trace in traces:
        spans = trace["spans"]
        assert len(spans) == 1
        for item in spans.items():
            span = item[1]
            validate_common_tags(span, use_128_bits_trace_id)
            if span["type"] == "web":
                server_span = span
            elif span["type"] == "custom":
                message_span = span
            else:
                raise Exception("Unexpected span ", span)
    validate_server_span(server_span)
    validate_message_span(message_span)
    validate_span_link(server_span, message_span)


def validate_common_tags(span: dict, use_128_bits_trace_id: bool):
    expected_tags = {
        "parent_id": "0",
        "env": "system-tests",
        "service": "otel-system-tests-spring-boot",
        "ingestion_reason": "otel",
    }
    expected_meta = {
        "env": "system-tests",
        "deployment.environment": "system-tests",
        "_dd.ingestion_reason": "otel",
        "otel.status_code": "Unset",
        "otel.user_agent": "OTel-OTLP-Exporter-Java/1.23.1",
        "otel.library.name": "com.datadoghq.springbootnative",
    }
    assert expected_tags.items() <= span.items()
    assert expected_meta.items() <= span["meta"].items()
    validate_trace_id(span, use_128_bits_trace_id)


def validate_trace_id(span: dict, use_128_bits_trace_id: bool):
    dd_trace_id = int(span["trace_id"], base=10)
    otel_trace_id = int(span["meta"]["otel.trace_id"], base=16)
    if use_128_bits_trace_id:
        assert dd_trace_id == otel_trace_id
    else:
        trace_id_bytes = otel_trace_id.to_bytes(16, "big")
        assert dd_trace_id == int.from_bytes(trace_id_bytes[8:], "big")


def validate_server_span(span: dict):
    expected_tags = {"name": "WebController.home", "resource": "GET /"}
    expected_meta = {"http.route": "/", "http.method": "GET"}
    assert expected_tags.items() <= span.items()
    assert expected_meta.items() <= span["meta"].items()


def validate_message_span(span: dict):
    expected_tags = {"name": "WebController.home.publish", "resource": "publish"}
    expected_meta = {"messaging.operation": "publish", "messaging.system": "rabbitmq"}
    assert expected_tags.items() <= span.items()
    assert expected_meta.items() <= span["meta"].items()


def validate_span_link(server_span: dict, message_span: dict):
    span_links = json.loads(server_span["meta"]["_dd.span_links"])
    assert len(span_links) == 1
    span_link = span_links[0]
    assert span_link["trace_id"] == message_span["meta"]["otel.trace_id"]
    span_id_hex = f'{int(message_span["span_id"]):x}'  # span_id is an int in span but a hex in span_links
    assert span_link["span_id"] == span_id_hex
    assert span_link["attributes"] == {"messaging.operation": "publish"}
