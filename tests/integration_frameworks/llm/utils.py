import time
from unittest import mock

import requests

from utils import context
from utils.docker_fixtures import TestAgentAPI

from typing import TypedDict


class LlmObsSpanEvent(TypedDict, total=False):
    trace_id: str
    span_id: str
    parent_id: str
    name: str
    start_ns: int
    duration: int
    status: str
    meta: dict
    metrics: dict
    _dd: dict
    tags: list[str]


def assert_llmobs_span_event(
    actual_span_event: LlmObsSpanEvent,
    name: str,
    span_kind: str,
    trace_id: str | None = None,
    span_id: str | None = None,
    parent_id: str | None = None,
    input_messages: list[dict] | None = None,
    input_documents: list[dict] | None = None,
    input_value: str | None = None,
    output_messages: list[dict] | None = None,
    output_documents: list[dict] | None = None,
    output_value: str | None = None,
    metrics: dict | None = None,
    metadata: dict | None = None,
    tags: dict | None = None,
    ml_app: str | None = "test-app",
    session_id: str | None = None,
    integration: str | None = None,
    model_name: str | None = None,
    model_provider: str | None = None,
    tool_definitions: list[dict] | None = None,
    ignore_values: list[str] | None = None,
    *,
    error: bool = False,
    has_output: bool = True,
) -> None:
    # assert span kind, tags, and error separately
    actual_span_kind = actual_span_event["meta"].pop("span.kind", None) or actual_span_event["meta"].pop("span")["kind"]
    actual_tags: list[str] = actual_span_event.pop("tags")

    if error:
        if actual_span_event.get("meta", {}).get("error") is not None:
            error_meta = actual_span_event.get("meta", {}).pop("error")
            assert error_meta["message"] == mock.ANY
            assert error_meta["type"] == mock.ANY
            assert error_meta["stack"] == mock.ANY
        else:
            assert actual_span_event["meta"].pop("error.message") == mock.ANY
            assert actual_span_event["meta"].pop("error.type") == mock.ANY
            assert actual_span_event["meta"].pop("error.stack") == mock.ANY

    assert actual_span_kind == span_kind, f"Span kind expected '{span_kind}', got '{actual_span_kind}'"
    _assert_tags_span_event_tags(actual_tags, ml_app, session_id, integration, error=error, tags=tags)

    # assert diff of rest of span event
    expected_meta: dict = {
        "input": {},
    }

    if has_output:
        expected_meta["output"] = {}
    else:
        #  output can either not exist or be an empty object
        #  different llmobs sdks do this differently
        output = actual_span_event.get("meta", {}).pop("output", None)
        assert output is None or output == {}

    if input_messages is not None:
        expected_meta["input"]["messages"] = input_messages
    elif input_documents is not None:
        expected_meta["input"]["documents"] = input_documents
    elif input_value is not None:
        expected_meta["input"]["value"] = input_value

    if output_messages is not None:
        expected_meta["output"]["messages"] = output_messages
    elif output_documents is not None:
        expected_meta["output"]["documents"] = output_documents
    elif output_value is not None:
        expected_meta["output"]["value"] = output_value

    if metadata is not None:
        expected_meta["metadata"] = metadata

    if model_name is not None:
        expected_meta["model_name"] = model_name
    if model_provider is not None:
        expected_meta["model_provider"] = model_provider

    if tool_definitions is not None:
        expected_meta["tool_definitions"] = tool_definitions

    expected_span_event = {
        "trace_id": trace_id or mock.ANY,
        "span_id": span_id or mock.ANY,
        "parent_id": parent_id or mock.ANY,
        "name": name,
        "start_ns": mock.ANY,
        "duration": mock.ANY,
        "status": "error" if error else "ok",
        "meta": expected_meta,
        "metrics": metrics or {},
        "_dd": mock.ANY,
    }

    _strip_ignore_values(expected_span_event, ignore_values)

    assert actual_span_event == expected_span_event


def _strip_ignore_values(expected_span_event: dict, ignore_values: list[str] | None) -> None:
    if ignore_values is None:
        return

    for key in ignore_values:
        path = key.split(".")

        # iterate over path and set the value at the end of the path to mock.ANY
        current = expected_span_event
        for p in path[:-1]:
            current = current[p]
        current[path[-1]] = mock.ANY


def _assert_tags_span_event_tags(
    actual_tags: list[str],
    ml_app: str | None = "test-app",
    session_id: str | None = None,
    integration: str | None = None,
    tags: dict | None = None,
    *,
    error: bool = False,
) -> None:
    expected_tags = {
        "service": mock.ANY,
        "version": mock.ANY,
        "env": mock.ANY,
        "source": "integration",
        "ml_app": ml_app,
        "ddtrace.version": mock.ANY,
        "language": _library_to_language_tag(),
        "error": str(int(error)),
    }

    if tags is not None:
        expected_tags.update(tags)

    if session_id is not None:
        expected_tags["session_id"] = session_id

    if integration is not None:
        expected_tags["integration"] = integration

    if error:
        expected_tags["error_type"] = mock.ANY

    actual_tags_parsed = dict(tag.split(":") for tag in actual_tags)

    assert len(actual_tags_parsed) >= len(expected_tags)
    for key, value in expected_tags.items():
        assert actual_tags_parsed[key] == value, (
            f"Tag '{key}' expected value '{value}', got '{actual_tags_parsed[key]}'"
        )


def _library_to_language_tag() -> str:
    if context.library == "nodejs":
        return "javascript"

    if context.library == "java":
        return "jvm"

    return context.library.name


def assert_prompt_tracking(
    span_event: LlmObsSpanEvent,
    prompt_id: str,
    prompt_version: str,
    variables: dict,
    expected_chat_template: list[dict],
    expected_messages: list[dict],
) -> None:
    """Helper to assert prompt tracking metadata and template extraction.

    Validates:
    - Prompt metadata (id, version, variables)
    - chat_template reconstruction with {{variable}} placeholders
    - Rendered messages (with variables substituted)
    """
    assert "prompt" in span_event["meta"]["input"], "Expected 'prompt' in span_event['meta']['input']"

    actual_prompt = span_event["meta"]["input"]["prompt"]
    assert actual_prompt["id"] == prompt_id, f"Expected prompt id '{prompt_id}', got '{actual_prompt['id']}'"
    assert actual_prompt["version"] == prompt_version, (
        f"Expected prompt version '{prompt_version}', got '{actual_prompt['version']}'"
    )
    assert actual_prompt["variables"] == variables, f"Expected variables {variables}, got {actual_prompt['variables']}"

    assert "chat_template" in actual_prompt, "Expected 'chat_template' in prompt metadata"
    assert actual_prompt["chat_template"] == expected_chat_template, (
        f"Expected chat_template {expected_chat_template}, got {actual_prompt['chat_template']}"
    )

    assert span_event["meta"]["input"]["messages"] == expected_messages, (
        f"Expected messages {expected_messages}, got {span_event['meta']['input']['messages']}"
    )


# ---------------------------------------------------------------------------
# AI Guard
#
# Helpers shared by the AI Guard <-> LLM-SDK integration suites (OpenAI, Anthropic, ...).
# Every one of those suites asserts the same two things: that an ai_guard span was
# emitted for the evaluation point being exercised, and that the local root span carries
# the ai_guard.event:true marker. The polling helpers live here so each provider suite
# only holds the requests that are specific to its SDK.
# ---------------------------------------------------------------------------


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
