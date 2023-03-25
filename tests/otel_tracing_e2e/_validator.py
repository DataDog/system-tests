# Util functions to validate JSON trace data from OTel system tests


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
    # TODO: validate span links once the format is fixed in intake
    # validate_span_link(server_span, message_span)


def validate_common_tags(span: dict, use_128_bits_trace_id: bool):
    assert span["parent_id"] == "0"
    assert span["env"] == "system-tests"
    assert span["service"] == "otel-system-tests-spring-boot"
    assert span["meta"]["env"] == "system-tests"
    assert span["meta"]["deployment.environment"] == "system-tests"
    assert span["meta"]["_dd.ingestion_reason"] == "otel"
    assert span["ingestion_reason"] == "otel"
    assert span["meta"]["otel.status_code"] == "Unset"
    assert span["meta"]["otel.user_agent"] == "OTel-OTLP-Exporter-Java/1.23.1"
    assert span["meta"]["otel.library.name"] == "com.datadoghq.springbootnative"
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
    assert span["name"] == "WebController.home"
    assert span["resource"] == "GET /"
    assert span["meta"]["http.route"] == "/"
    assert span["meta"]["http.method"] == "GET"


def validate_message_span(span: dict):
    assert span["name"] == "WebController.home.publish"
    assert span["resource"] == "publish"
    assert span["meta"]["messaging.operation"] == "publish"
    assert span["meta"]["messaging.system"] == "rabbitmq"


def validate_span_link(server_span: dict, message_span: dict):
    span_links = server_span["meta"]["_dd.span_links"]
    assert len(span_links) == 1
    span_link = span_links[0]
    assert span_link["trace_id"] == message_span["meta"]["otel.trace_id"]
    assert span_link["span_id"] == message_span["span_id"]
    assert span_link["attributes"] == {"messaging.operation": "publish"}
