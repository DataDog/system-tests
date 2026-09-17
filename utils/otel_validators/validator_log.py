# Util functions to validate JSON logs from OTel system tests


def validate_log(log: dict, rid: str, otel_source: str) -> dict:
    """Validates the JSON logs from backend and returns the OTel log trace attributes"""

    if otel_source in ("datadog_agent", "datadog_exporter"):
        assert log["ddtags"] == f"env:system-tests,service:otel-system-tests-spring-boot,otel_source:{otel_source}"

        # assert expected_attributes_tags <= log["attributes"]["tags"]

        assert log["message"]["http.request.headers.user-agent"] == f"system_tests rid/{rid}"
        assert log["message"]["http.method"] == "GET"
        assert log.get("status") == "info"

        return log["message"]
    if otel_source == "backend_endpoint":
        attributes = {a["key"]: a["value"] for a in log["attributes"]}
        assert attributes["http.request.headers.user-agent"] == {"stringValue": f"system_tests rid/{rid}"}
        assert attributes["http.method"] == {"stringValue": "GET"}

        return log
    raise TypeError(f"Unknown source: {otel_source}")


def validate_log_trace_correlation(otel_log_trace_attrs: dict, trace: dict, otel_source: str) -> None:
    if otel_source == "datadog_agent":
        assert len(trace["spans"]) == 1
        span = trace["spans"][0]
        assert span is not None
        assert otel_log_trace_attrs["otel.trace_id"] == span["meta"]["otel.trace_id"], span["meta"]
        assert otel_log_trace_attrs["dd.span_id"] == span["spanID"]
        assert str(otel_log_trace_attrs["otel.severity_number"]) == "9"
    elif otel_source == "backend_endpoint":
        assert len(trace["spans"]) == 1
        span = trace["spans"][0]
        assert span is not None
        assert otel_log_trace_attrs["traceId"] == span["traceId"]
        assert otel_log_trace_attrs["spanId"] == span["spanId"]
        assert str(otel_log_trace_attrs["severityNumber"]) == "9"
    else:
        raise TypeError(f"Unknown source: {otel_source}")
