import json

# Util functions to validate JSON trace data from OTel system tests


def validate_trace(trace_data, dd_trace_id, root_span_id, otel_trace_id):
    assert root_span_id == int(trace_data["root_id"])
    spans = trace_data["spans"]
    assert len(spans) == 3
    root_span = None
    server_span = None
    message_span = None
    for item in spans.items():
        span_id = item[0]
        span = item[1]
        validate_common_tags(span, dd_trace_id, otel_trace_id)
        if int(span_id) == root_span_id:
            root_span = span
        elif span["type"] == "web":
            server_span = span
        elif span["type"] == "custom":
            message_span = span
        else:
            raise Exception("Unexpected span ", span)
    validate_root_span(root_span, server_span["span_id"], message_span["span_id"])
    validate_server_span(server_span, root_span_id)
    validate_message_span(message_span, root_span_id)
    # TODO: validate span links once the format is fixed in intake
    # validate_span_link(server_span, message_span, otel_trace_id)


def validate_common_tags(span, dd_trace_id, otel_trace_id):
    assert int(span["trace_id"]) == dd_trace_id
    assert int(span["meta"]["otel.trace_id"], base=16) == otel_trace_id
    assert span["env"] == "system-tests"
    assert span["meta"]["env"] == "system-tests"
    assert span["meta"]["deployment.environment"] == "system-tests"
    assert span["meta"]["_dd.ingestion_reason"] == "otel"
    assert span["ingestion_reason"] == "otel"
    assert span["meta"]["otel.status_code"] == "STATUS_CODE_UNSET"


def validate_root_span(span, server_span_id, message_span_id):
    assert span["parent_id"] == "0"
    assert span["type"] == "http"
    assert span["service"] == "system-tests-runner"
    assert span["name"] == "runner.get"
    assert span["resource"] == "GET"
    assert span["meta"]["otel.user_agent"] == "OTel-OTLP-Exporter-Python/1.16.0"
    assert span["meta"]["otel.library.name"] == "system-tests-runner"
    assert span["meta"]["telemetry.sdk.name"] == "opentelemetry"
    assert span["meta"]["telemetry.sdk.language"] == "python"
    assert span["meta"]["telemetry.sdk.version"] == "1.16.0"
    assert span["meta"]["http.status_code"] == "200"
    assert span["meta"]["http.host"] == "weblog"
    assert span["meta"]["http.url"] == "http://weblog:7777"
    assert span["meta"]["http.method"] == "GET"
    assert len(span["children_ids"]) == 2
    assert server_span_id in span["children_ids"]
    assert message_span_id in span["children_ids"]


def validate_server_span(span, root_span_id):
    assert int(span["parent_id"]) == root_span_id
    assert span["type"] == "web"
    assert span["service"] == "otel-system-tests-spring-boot"
    assert span["name"] == "WebController.home"
    assert span["resource"] == "GET /"
    assert span["meta"]["otel.user_agent"] == "OTel-OTLP-Exporter-Java/1.23.1"
    assert span["meta"]["otel.library.name"] == "com.datadoghq.springbootnative"
    assert span["meta"]["http.route"] == "/"
    assert span["meta"]["http.method"] == "GET"


def validate_message_span(span, root_span_id):
    assert int(span["parent_id"]) == root_span_id
    assert span["type"] == "custom"
    assert span["service"] == "otel-system-tests-spring-boot"
    assert span["name"] == "WebController.home.publish"
    assert span["resource"] == "publish"
    assert span["meta"]["otel.user_agent"] == "OTel-OTLP-Exporter-Java/1.23.1"
    assert span["meta"]["otel.library.name"] == "com.datadoghq.springbootnative"
    assert span["meta"]["messaging.operation"] == "publish"
    assert span["meta"]["messaging.system"] == "rabbitmq"


def validate_span_link(server_span, message_span, otel_trace_id):
    span_links = json.load(server_span["meta"]["_dd.span_links"])
    assert len(span_links) == 1
    span_link = span_links[0]
    assert int(span_link["trace_id"], base=16) == otel_trace_id
    assert span_link["span_id"] == message_span["span_id"]
    assert span_link["attributes"] == {"messaging.operation": "publish"}
