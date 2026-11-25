from __future__ import annotations

import time

import requests

from utils import irrelevant, context
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils import TestAgentAPI
    from tests.integration_frameworks.llm.utils import LlmObsSpanEvent


@irrelevant("litellm" not in context.weblog_variant)
class BaseLitellmTest: ...


def _llmobs_span_events(test_agent: TestAgentAPI) -> list[LlmObsSpanEvent] | None:
    try:
        llmobs_requests = test_agent.llmobs_requests()
    except requests.exceptions.RequestException:
        return None
    return [span for request in llmobs_requests for event in request for span in event["spans"]]


def wait_for_llmobs_span_events(
    test_agent: TestAgentAPI, num: int, wait_loops: int = 50, settle_loops: int = 5
) -> list[LlmObsSpanEvent]:
    """Poll until num span events arrived, then settle_loops more, so a late event also fails the count."""
    span_events: list[LlmObsSpanEvent] = []
    for _ in range(wait_loops):
        span_events = _llmobs_span_events(test_agent) or span_events
        if len(span_events) >= num:
            break
        time.sleep(0.1)
    else:
        return sorted(span_events, key=lambda span: span["start_ns"])

    for _ in range(settle_loops):
        time.sleep(0.1)
        span_events = _llmobs_span_events(test_agent) or span_events
    return sorted(span_events, key=lambda span: span["start_ns"])


def span_kind(span_event: LlmObsSpanEvent) -> str | None:
    meta = span_event["meta"]
    return meta.get("span.kind") or meta.get("span", {}).get("kind")


def gateway(span_event: LlmObsSpanEvent) -> str | None:
    metadata_dd = (span_event["meta"].get("metadata") or {}).get("_dd")
    return metadata_dd.get("gateway") if isinstance(metadata_dd, dict) else None


def assert_gateway_marker(span_events: list[LlmObsSpanEvent], expected: str | None) -> None:
    """Only the llm span has the gateway marker, and no span event has a tag about the gateway."""
    for span_event in span_events:
        expected_gateway = expected if span_kind(span_event) == "llm" else None
        assert gateway(span_event) == expected_gateway, (
            f"Span event '{span_event['name']}' of kind '{span_kind(span_event)}' has gateway "
            f"'{gateway(span_event)}', expected '{expected_gateway}'"
        )
        gateway_tags = [tag for tag in span_event["tags"] if "gateway" in tag]
        assert not gateway_tags, f"Span event '{span_event['name']}' has gateway tags {gateway_tags}"
