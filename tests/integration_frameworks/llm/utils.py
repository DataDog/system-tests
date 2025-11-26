from unittest import mock
from utils import context

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

    assert len(actual_tags_parsed) == len(expected_tags)
    for key, value in expected_tags.items():
        assert actual_tags_parsed[key] == value, (
            f"Tag '{key}' expected value '{value}', got '{actual_tags_parsed[key]}'"
        )


def _library_to_language_tag() -> str:
    if context.library == "nodejs":
        return "javascript"

    return context.library.name
