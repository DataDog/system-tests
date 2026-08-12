"""Helpers shared by the AI Guard <-> LLM-SDK integration suites (OpenAI, Anthropic, ...).

Every one of those suites asserts the same two things: that an ``ai_guard`` span was emitted
for the evaluation point being exercised, and that the local root span carries the
``ai_guard.event:true`` marker. The polling helpers live here so each provider suite only
holds the requests that are specific to its SDK.
"""

import time

import requests

from utils.docker_fixtures import TestAgentAPI


def ai_guard_spans(traces: list[list[dict]]) -> list[dict]:
    return [span for trace in traces for span in trace if span.get("resource") == "ai_guard"]


def guard_messages(span: dict) -> list[dict]:
    """The messages AI Guard evaluated, as captured in meta_struct.ai_guard.messages."""
    return span.get("meta_struct", {}).get("ai_guard", {}).get("messages", [])


def ai_guard_event_root_spans(traces: list[list[dict]]) -> list[dict]:
    """Local root (service-entry) spans tagged ai_guard.event:true.

    When AI Guard evaluates a call it tags the trace's local root span with
    ai_guard.event:true (dd-trace-py aiguard/_api_client.py). This is a tracer-emitted
    marker that AI Guard ran on the trace, and is what we assert on here.

    Note: the _dd.ai_guard.enabled:1 facet that is searchable in the Datadog UI is NOT
    present in the raw payloads captured by the test agent (it is not emitted by the tracer;
    it is produced somewhere in intake), so it cannot be asserted on directly.
    """
    return [
        span
        for trace in traces
        for span in trace
        if span.get("parent_id") in (0, None) and span.get("meta", {}).get("ai_guard.event", False) in (True, "true")
    ]


def wait_for_ai_guard_spans(test_agent: TestAgentAPI, *, target: str | None = None, wait_loops: int = 30) -> list[dict]:
    """Poll the test agent until at least one matching ai_guard span is received.

    We assert on the presence of the ai_guard span rather than on a fixed number of traces:
    the tracer does not deterministically group the ai_guard span with the LLM SDK span. The
    ai_guard span may be emitted either nested in the SDK trace (1 trace) or as its own trace
    (2 traces), so wait_for_num_traces with a hard-coded count is inherently racy. When target
    is given, only spans whose ai_guard.target matches are considered (so we keep polling until
    the specific evaluation point we care about has arrived).
    """
    spans: list[dict] = []
    for _ in range(wait_loops):
        try:
            traces = test_agent.traces(clear=False)
        except requests.exceptions.RequestException:
            pass
        else:
            spans = ai_guard_spans(traces)
            if target is not None:
                spans = [span for span in spans if span["meta"].get("ai_guard.target") == target]
            if spans:
                return spans
        time.sleep(0.1)
    return spans


def wait_for_ai_guard_event_root_spans(test_agent: TestAgentAPI, *, wait_loops: int = 30) -> list[dict]:
    """Poll the test agent until at least one root span tagged ai_guard.event:true arrives.

    Like the ai_guard span itself, the tagged local root span may land in a later trace chunk
    than the evaluation span, so we poll rather than reading a single snapshot.
    """
    spans: list[dict] = []
    for _ in range(wait_loops):
        try:
            traces = test_agent.traces(clear=False)
        except requests.exceptions.RequestException:
            pass
        else:
            spans = ai_guard_event_root_spans(traces)
            if spans:
                return spans
        time.sleep(0.1)
    return spans
