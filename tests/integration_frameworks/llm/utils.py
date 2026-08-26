import time
from unittest import mock

import requests

from utils import context
from utils.docker_fixtures import TestAgentAPI

from collections.abc import Callable
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


# AI Guard helpers shared by the provider integration suites (OpenAI, Anthropic, ...). DD_API_KEY /
# DD_APP_KEY come from the scenario env, not library_env, which is copied into the JSON report.
AI_GUARD_LIBRARY_ENV: dict[str, str] = {"DD_AI_GUARD_ENABLED": "true"}


def assert_ai_guard_evaluated(test_agent: TestAgentAPI, *, target: str) -> list[dict]:
    """Assert an ai_guard span for target was emitted and the local root span is tagged ai_guard.event:true.

    The spans may land nested in the SDK trace or in their own, so poll rather than wait on a trace count.
    """
    spans = _wait_for(test_agent, lambda traces: _ai_guard_spans(traces, target))
    assert spans, f"expected an ai_guard span with target '{target}'"

    assert _wait_for(test_agent, _ai_guard_event_root_spans), "expected a local root span tagged ai_guard.event:true"

    return spans


def assert_assistant_tool_calls_forwarded(guard_spans: list[dict]) -> None:
    """Assert the SDK tool-call blocks were converted and sent to AI Guard.

    A target "tool" span alone is not enough: it can also come from an after-model eval.
    """
    assert any(
        message.get("role") == "assistant" and message.get("tool_calls")
        for span in guard_spans
        for message in _guard_messages(span)
    ), "expected the assistant tool_calls entry in the ai_guard evaluation payload"


def _ai_guard_spans(traces: list[list[dict]], target: str | None = None) -> list[dict]:
    return [
        span
        for trace in traces
        for span in trace
        if span.get("resource") == "ai_guard"
        and (target is None or span.get("meta", {}).get("ai_guard.target") == target)
    ]


def _ai_guard_event_root_spans(traces: list[list[dict]]) -> list[dict]:
    """Local root spans tagged ai_guard.event:true, the tracer's marker that AI Guard ran on the trace.

    The _dd.ai_guard.enabled:1 facet from the Datadog UI comes from intake, so it is not in these payloads.
    """
    return [
        span
        for trace in traces
        for span in trace
        if span.get("parent_id") in (0, None) and span.get("meta", {}).get("ai_guard.event", False) in (True, "true")
    ]


def _guard_messages(span: dict) -> list[dict]:
    """The messages AI Guard evaluated, as captured in meta_struct.ai_guard.messages."""
    return span.get("meta_struct", {}).get("ai_guard", {}).get("messages", [])


def _wait_for(
    test_agent: TestAgentAPI, select: Callable[[list[list[dict]]], list[dict]], wait_loops: int = 30
) -> list[dict]:
    """Poll the test agent until select() matches at least one span, or give up and return []."""
    spans: list[dict] = []
    for _ in range(wait_loops):
        try:
            traces = test_agent.traces(clear=False)
        except requests.exceptions.RequestException:
            pass
        else:
            spans = select(traces)
            if spans:
                return spans
        time.sleep(0.1)
    return spans
