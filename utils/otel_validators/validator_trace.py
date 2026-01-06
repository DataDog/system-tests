# Util functions to validate JSON trace data from OTel system tests

import json
import dictdiffer
from utils._logger import logger


# Validates traces from Agent, Collector and Backend intake OTLP ingestion paths are consistent
def validate_all_traces(
    traces_agent: list[dict], traces_intake: list[dict], traces_collector: list[dict], *, use_128_bits_trace_id: bool
) -> None:
    spans_agent = validate_trace(traces_agent, use_128_bits_trace_id=use_128_bits_trace_id)
    spans_intake = validate_trace(traces_intake, use_128_bits_trace_id=use_128_bits_trace_id)
    spans_collector = validate_trace(traces_collector, use_128_bits_trace_id=use_128_bits_trace_id)
    validate_spans_from_all_paths(spans_agent, spans_intake, spans_collector)


# Validates fields that we know the values upfront for one single trace from an OTLP ingestion path
def validate_trace(traces: list[dict], *, use_128_bits_trace_id: bool) -> tuple:
    server_span = None
    message_span = None
    for trace in traces:
        spans = trace["spans"]
        assert len(spans) == 1
        for item in spans.items():
            span = item[1]
            validate_common_tags(span, use_128_bits_trace_id=use_128_bits_trace_id)
            if span["type"] == "web":
                server_span = span
            elif span["type"] == "custom":
                message_span = span
            else:
                raise ValueError("Unexpected span ", span)

    assert server_span is not None
    assert message_span is not None

    validate_server_span(server_span)
    validate_message_span(message_span)
    validate_span_link(server_span, message_span)
    return (server_span, message_span)


def validate_common_tags(span: dict, *, use_128_bits_trace_id: bool) -> None:
    assert span["parent_id"] == "0"
    assert span["service"] == "otel-system-tests-spring-boot"
    expected_meta = {
        "deployment.environment": "system-tests",
        "otel.status_code": "Unset",
        "otel.library.name": "com.datadoghq.springbootnative",
    }
    assert expected_meta.items() <= span["meta"].items()
    validate_trace_id(span, use_128_bits_trace_id=use_128_bits_trace_id)


def validate_trace_id(span: dict, *, use_128_bits_trace_id: bool) -> None:
    dd_trace_id = int(span["trace_id"], base=10)
    otel_trace_id = int(span["meta"]["otel.trace_id"], base=16)
    if use_128_bits_trace_id:
        assert dd_trace_id == otel_trace_id
    else:
        trace_id_bytes = otel_trace_id.to_bytes(16, "big")
        assert dd_trace_id == int.from_bytes(trace_id_bytes[8:], "big")


def validate_server_span(span: dict) -> None:
    expected_tags = {"name": "WebController.basic", "resource": "GET /"}
    expected_meta = {"http.route": "/", "http.method": "GET"}
    assert expected_tags.items() <= span.items()
    assert expected_meta.items() <= span["meta"].items()


def validate_message_span(span: dict) -> None:
    expected_tags = {"name": "WebController.basic.publish", "resource": "publish"}
    expected_meta = {"messaging.operation": "publish", "messaging.system": "rabbitmq"}
    assert expected_tags.items() <= span.items()
    assert expected_meta.items() <= span["meta"].items()


def validate_span_link(server_span: dict, message_span: dict) -> None:
    # TODO: enable check on span links once newer version of Agent is used in system tests
    if "_dd.span_links" not in server_span["meta"]:
        return

    links = json.loads(server_span["meta"]["_dd.span_links"])
    assert len(links) == 1
    link = links[0]
    assert link["trace_id"] == message_span["meta"]["otel.trace_id"]
    assert int(link["span_id"], 16) == int(message_span["span_id"])
    assert link["attributes"] == {"messaging.operation": "publish"}


# Validates fields that we don't know the values upfront for all 3 ingestion paths
def validate_spans_from_all_paths(spans_agent: tuple, spans_intake: tuple, spans_collector: tuple) -> None:
    validate_span_fields(spans_agent[0], spans_intake[0], "Agent server span", "Intake server span")
    validate_span_fields(spans_agent[0], spans_collector[0], "Agent server span", "Collector server span")
    validate_span_fields(spans_agent[1], spans_intake[1], "Agent message span", "Intake message span")
    validate_span_fields(spans_agent[1], spans_collector[1], "Agent message span", "Collector message span")


def validate_span_fields(span1: dict, span2: dict, name1: str, name2: str) -> None:
    logger.debug(f"Validate span fields. [{name1}]:[{span1}]")
    logger.debug(f"Validate span fields. [{name2}]:[{span2}]")
    assert span1["start"] == span2["start"]
    assert span1["end"] == span2["end"]
    assert span1["duration"] == span2["duration"]
    assert span1["resource_hash"] == span2["resource_hash"]
    validate_span_metas_metrics(span1["meta"], span2["meta"], span1["metrics"], span2["metrics"], name1, name2)


KNOWN_UNMATCHED_METAS = [
    "env",
    "ddtags",
    "otel.user_agent",
    "otel.source",
    "span.kind",
    "_dd.agent_version",
    "_dd.agent_rare_sampler.enabled",
    "_dd.hostname",
    "_dd.compute_stats",
    "_dd.tracer_version",
    "_dd.p.dm",
    "_dd.agent_hostname",
    "_dd.ingestion_reason",  # this is replaced by `ddtags: ingestion_reason:otel` in the latest version
    "_dd.install.id",
    "_dd.install.time",
    "_dd.install.type",
    "_dd.p.tid",
]
KNOWN_UNMATCHED_METRICS = [
    "_dd.agent_errors_sampler.target_tps",
    "_dd.agent_priority_sampler.target_tps",
    "_sampling_priority_rate_v1",
    "_dd.otlp_sr",
    "_top_level",
]


def validate_span_metas_metrics(
    meta1: dict, meta2: dict, metrics1: dict, metrics2: dict, name1: str, name2: str
) -> None:
    # Exclude fields that are expected to have different values for different ingestion paths
    for known_unmatched_meta in KNOWN_UNMATCHED_METAS:
        meta1.pop(known_unmatched_meta, None)
        meta2.pop(known_unmatched_meta, None)
    for known_unmatched_metric in KNOWN_UNMATCHED_METRICS:
        metrics1.pop(known_unmatched_metric, None)
        metrics2.pop(known_unmatched_metric, None)

    # Other fields should match
    assert meta1 == meta2, f"Diff in metas between {name1} and {name2}: {list(dictdiffer.diff(meta1, meta2))}"
    assert metrics1 == metrics2, (
        f"Diff in metrics between {name1} and {name2}: {list(dictdiffer.diff(metrics1, metrics2))}"
    )
