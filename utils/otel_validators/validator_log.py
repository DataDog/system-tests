# Util functions to validate JSON logs from OTel system tests


def validate_log(log: dict, rid: str, otel_source: str) -> dict:
    """Validates the JSON logs from backend and returns the OTel log trace attributes"""
    assert log["type"] == "log"
    expected_attributes_tags = [
        "datadog.submission_auth:api_key",
        "datadog.index:main",
        "env:system-tests",
        f"otel_source:{otel_source}",
        "service:otel-system-tests-spring-boot",
        "source:otlp_log_ingestion",
    ]
    assert expected_attributes_tags <= log["attributes"]["tags"]

    assert log["attributes"]["attributes"]["http"]["request"]["headers"]["user-agent"] == f"system_tests rid/{rid}"
    assert log["attributes"]["attributes"]["http"]["method"] == "GET"
    assert log["attributes"]["attributes"].get("status") == "info" or log["attributes"].get("status") == "info"

    return log["attributes"]["attributes"]["otel"]


def validate_log_trace_correlation(otel_log_trace_attrs: dict, trace: dict) -> None:
    assert len(trace["spans"]) == 1
    span = None
    for item in trace["spans"].items():
        span = item[1]
    assert span is not None
    assert otel_log_trace_attrs["trace_id"] == span["meta"]["otel.trace_id"]
    assert int(otel_log_trace_attrs["span_id"], 16) == int(span["span_id"])
    assert str(otel_log_trace_attrs["severity_number"]) == "9"
