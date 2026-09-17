# Util functions to validate JSON logs from OTel system tests


def validate_log(log: dict, rid: str, otel_source: str) -> dict:
    """Validates the JSON logs from backend and returns the OTel log trace attributes"""

    assert log["ddtags"] == f"env:system-tests,service:otel-system-tests-spring-boot,otel_source:{otel_source}"

    # assert expected_attributes_tags <= log["attributes"]["tags"]

    assert log["message"]["http.request.headers.user-agent"] == f"system_tests rid/{rid}"
    assert log["message"]["http.method"] == "GET"
    assert log.get("status") == "info"

    return log["message"]


def validate_log_trace_correlation(otel_log_trace_attrs: dict, trace: dict) -> None:
    assert len(trace["spans"]) == 1
    span = trace["spans"][0]
    assert span is not None
    assert otel_log_trace_attrs["otel.trace_id"] == span["meta"]["otel.trace_id"], span["meta"]
    assert otel_log_trace_attrs["dd.span_id"] == span["spanID"]
    assert str(otel_log_trace_attrs["otel.severity_number"]) == "9"
