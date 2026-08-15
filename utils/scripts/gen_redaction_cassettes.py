#!/usr/bin/env python3
"""Generate hand-crafted AI Guard redaction VCR cassettes.

The VCR proxy (dd-apm-test-agent) resolves an incoming request to a cassette file
named `{safe_path}_{method}_{hash8}.json`, where:

    safe_path = "aiguard/evaluate" with "/" -> "_"  => "aiguard_evaluate"
    method    = request method lower-cased          => "post"
    hash8     = sha256("aiguard/evaluate:POST:" + json.dumps(body, sort_keys=True)).hexdigest()[:8]

`body` is the exact JSON the tracer POSTs, i.e.
    {"data": {"attributes": {"messages": <verbatim messages>,
                             "meta": {"service": "weblog", "env": "system-tests"}}}}

This mirrors the AI Guard Sensitive Data Redaction RFC: the backend returns a
top-level `redaction_replacements` array (one entry per redacted path, already
fully redacted) alongside the informative `sds_findings` detection metadata.

Besides the cassettes, this writes tests/ai_guard/redaction_scenarios.json, which
carries the expected outcome of every scenario: the messages after redaction, the
sensitive values that must be gone, the ones that must survive, and whether the
tracer must report the evaluation as redacted (the ai_guard.redacted span tag and
the redacted telemetry tag).

Every one of those expectations is authored in SCENARIOS below (expect_redacted and
expect_removed) and cross-checked against apply_replacements, a reference
implementation of the RFC algorithm. The two are kept independent on purpose: a
corpus that only ever reported what the reference implementation happened to do
would assert tracer == generator instead of tracer == RFC.

Run from the repo root:  python3 utils/scripts/gen_redaction_cassettes.py
Pass --check to report drift without writing anything (used by format.sh --check).
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path

CASSETTES_DIR = Path("utils/build/docker/vcr/cassettes/aiguard")
PLACEHOLDER = "<REDACTED>"

# rule catalog: value -> (rule_display_name, rule_tag, category)
RULES = {
    "ssn": ("US Social Security Number Scanner", "us_ssn", "ssn"),
    "email": ("Standard Email Address Scanner", "email_address", "email_address"),
    "phone": ("Phone Number Scanner", "phone_number", "phone_number"),
    "bank": ("Bank Account Number Scanner", "bank_account", "bank_account"),
    "credit_card": ("Credit Card Scanner", "credit_card", "credit_card"),
}


# ---------------------------------------------------------------------------
# Reference implementation of the RFC redaction algorithm
# ---------------------------------------------------------------------------

# One segment of a location path: a field name plus an optional non-negative list index.
# Always matched with fullmatch, never search: a partial match is rejected, and unlike $ that
# also rejects a trailing newline. The test-side resolver anchors with \Z for the same reason.
SEGMENT_RE = re.compile(r"(?P<name>[A-Za-z0-9_]+)(?:\[(?P<index>[0-9]+)\])?")

# The only terminal field names a replacement may be written to, per the RFC "Redactable
# targets" section: message content, content-part text and tool call arguments. Anything
# else resolves read-only, so an image locator, a role or a tool name is never overwritten
# even though it is a string.
REDACTABLE_TERMINALS = frozenset({"content", "text", "arguments"})

# Marks a path the backend sent conflicting replacements for: skipped rather than guessed.
_SKIP = object()


def _split_segments(path: str) -> list[tuple[str, int | None]] | None:
    """Split a location path into (name, index) segments, or None if any segment is malformed."""
    segments = []
    for raw in path.split("."):
        match = SEGMENT_RE.fullmatch(raw)
        if match is None:
            return None
        index = match.group("index")
        segments.append((match.group("name"), int(index) if index is not None else None))
    return segments


def _step(node: object, name: str, index: int | None) -> object:
    """Resolve one path segment, None whenever the field or the list index does not exist."""
    value = node.get(name) if isinstance(node, dict) else None
    if value is None or index is None:
        return value
    # Strictly a list: a generic subscript check would happily index into a string.
    if not isinstance(value, list) or index >= len(value):
        return None
    return value[index]


def _resolve_writable_string(root: dict, path: str) -> tuple[object, str | int] | None:
    """Resolve path to the (container, key) of a writable string, or None to skip it fail-safe."""
    segments = _split_segments(path)
    if not segments:
        return None

    name, index = segments[-1]
    if name not in REDACTABLE_TERMINALS:
        return None

    node: object = root
    for parent_name, parent_index in segments[:-1]:
        node = _step(node, parent_name, parent_index)
        if node is None:
            return None

    value = node.get(name) if isinstance(node, dict) else None
    if index is None:
        container: object = node
        key: str | int = name
        target = value
    else:
        if not isinstance(value, list) or index >= len(value):
            return None
        container = value
        key = index
        target = value[index]

    if not isinstance(target, str) or not isinstance(container, (dict, list)):
        return None
    return container, key


def _collect_replacements(replacements: object) -> dict[str, str | object]:
    """Collect one authoritative replacement per path, or _SKIP when the backend contradicts itself."""
    if not isinstance(replacements, list):
        return {}

    by_path: dict[str, str | object] = {}
    for entry in replacements:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        replacement = entry.get("replacement")
        # An empty replacement is valid: it is the customer's "remove" placeholder. A non-string
        # one is not, and would break serialization further down the line.
        if not path or not isinstance(path, str) or not isinstance(replacement, str):
            continue
        previous = by_path.get(path)
        if previous is not None and previous != replacement:
            by_path[path] = _SKIP
            continue
        by_path[path] = replacement
    return by_path


def apply_replacements(messages: list, replacements: object) -> tuple[list, bool]:
    """Apply replacements to messages, returning (redacted_messages, at_least_one_applied).

    Copy-on-write, and fail-safe: a malformed entry, an unresolvable path, a non-string or
    non-redactable target and conflicting replacements for one path are all skipped instead
    of raising. When nothing is applied the original list is returned unchanged.
    """
    if not replacements:
        return messages, False

    by_path = _collect_replacements(replacements)
    if not by_path:
        return messages, False

    result = copy.deepcopy(messages)
    root = {"messages": result}
    applied = 0
    for path, replacement in by_path.items():
        if replacement is _SKIP:
            continue
        resolved = _resolve_writable_string(root, path)
        if resolved is None:
            continue
        container, key = resolved
        container[key] = replacement  # type: ignore[index]
        applied += 1

    return (result, True) if applied else (messages, False)


# ---------------------------------------------------------------------------
# Cassette building
# ---------------------------------------------------------------------------


def _wrap_request_body(messages: list) -> str:
    return json.dumps(
        {"data": {"attributes": {"messages": messages, "meta": {"service": "weblog", "env": "system-tests"}}}}
    )


def _cassette_name(request_body: str) -> str:
    parsed = json.loads(request_body)
    details = f"aiguard/evaluate:POST:{json.dumps(parsed, sort_keys=True)}"
    digest = hashlib.sha256(details.encode()).hexdigest()[:8]
    return f"aiguard_evaluate_post_{digest}.json"


def _findings_for(path: str, sensitive: list[tuple[str, str]], text: str) -> list[dict]:
    """Build sds_findings for the (value, rule_key) pairs found in `text` at `path`.

    One finding per occurrence, because _redact replaces them all: reporting only the first would
    make the cassette contradict itself, with a replacement that removed a span no finding covers.
    """
    findings = []
    for value, rule_key in sensitive:
        display, tag, category = RULES[rule_key]
        start = text.find(value)
        assert start >= 0, f"{value!r} does not appear at {path}"
        while start >= 0:
            findings.append(
                {
                    "rule_display_name": display,
                    "rule_tag": tag,
                    "category": category,
                    "location": {
                        "path": path,
                        "start_index": start,
                        "end_index_exclusive": start + len(value),
                    },
                }
            )
            start = text.find(value, start + len(value))
    return findings


def _redact(text: str, sensitive: list[tuple[str, str]], placeholder: str) -> str:
    # Order-independent only while no value contains another: redacting the shorter one first would
    # otherwise leave a mangled fragment of the longer one behind.
    values = [value for value, _ in sensitive]
    for value in values:
        others = [other for other in values if other != value]
        assert not any(value in other for other in others), f"{value!r} is a substring of another declared value"

    redacted = text
    for value in values:
        redacted = redacted.replace(value, placeholder)
    return redacted


# The attack categories an evaluation scores, all at zero: redaction is orthogonal to attack
# detection, so a scenario matches no category unless it declares one in `tags`. tag_probs is part
# of the real evaluation response, so we keep it for deserializer parity.
_TAG_PROBS = {
    "authority-override": 0.0,
    "data-exfiltration": 0.0,
    "denial-of-service-tool-call": 0.0,
    "destructive-tool-call": 0.0,
    "indirect-prompt-injection": 0.0,
    "instruction-override": 0.0,
    "jailbreak": 0.0,
    "obfuscation": 0.0,
    "role-play": 0.0,
    "security-exploit": 0.0,
    "system-prompt-extraction": 0.0,
}

# The probability the backend reports for a category it did return. A returned tag can never keep
# its 0.0: Test_Tag_Probabilities requires every tag in `tags` to carry a positive probability, and
# an evaluation that matched a category by definition scored it above zero.
MATCHED_TAG_PROBABILITY = 0.97


def _tag_probs_for(tags: list[str]) -> dict[str, float]:
    """Build the tag_probs map, scoring every returned tag above zero."""
    probs = dict(_TAG_PROBS)
    for tag in tags:
        assert tag in probs, f"unknown attack category {tag!r}"
        probs[tag] = MATCHED_TAG_PROBABILITY
    assert all(probs[tag] > 0 for tag in tags), f"a returned tag has no positive probability: {tags}"
    return probs


def _response_body(
    *,
    action: str,
    reason: str,
    redaction_replacements: list | None,
    sds_findings: list,
    tags: list[str],
    tag_probs: dict[str, float],
) -> str:
    attributes: dict = {
        "action": action,
        "is_blocking_enabled": True,
        "reason": reason,
    }
    # None means the backend omitted the field entirely, which the RFC treats exactly like an
    # empty array. Both shapes are exercised by the corpus.
    if redaction_replacements is not None:
        attributes["redaction_replacements"] = redaction_replacements
    attributes["sds_findings"] = sds_findings
    attributes["tag_probs"] = tag_probs
    attributes["tags"] = tags
    return json.dumps({"data": {"id": "redaction-fixture", "type": "evaluations", "attributes": attributes}})


def _string_at_path(messages: list, path: str) -> str:
    """Minimal resolver for the paths used in the fixtures (mirrors the RFC path grammar)."""
    obj: object = {"messages": messages}
    for segment in path.split("."):
        m = SEGMENT_RE.fullmatch(segment)
        assert m, f"bad segment {segment!r}"
        obj = obj[m.group("name")]  # type: ignore[index]
        if m.group("index") is not None:
            obj = obj[int(m.group("index"))]  # type: ignore[index]
    assert isinstance(obj, str), f"path {path} did not resolve to a string"
    return obj


def render_cassette(request_body: str, response_body: str) -> str:
    """Render the cassette file content for one request/response pair."""
    cassette = {
        "request": {
            "method": "POST",
            "url": "https://app.datadoghq.com/api/v2/ai-guard/evaluate",
            "headers": {
                "Content-Type": "application/json",
                "DD-AI-GUARD-SOURCE": "SDK",
            },
            "body": request_body,
        },
        "response": {
            "status": {"code": 200, "message": "OK"},
            "headers": {
                "content-type": "application/vnd.api+json",
                "content-length": str(len(response_body.encode())),
            },
            "body": response_body,
        },
    }
    return json.dumps(cassette, indent=1) + "\n"


REDACTION_REASON = "Sensitive data detected; configured categories will be redacted."
NO_MATCH_REASON = "No rule match."
DENY_REASON = "Sensitive data exfiltration attempt detected."

_IMAGE_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

# Every scenario produces one cassette and one entry in the sidecar consumed by
# tests/ai_guard/test_ai_guard_sdk.py. Keys:
#   messages        what the weblog POSTs, and therefore what the cassette is keyed on
#   targets         (path, [(sensitive_value, rule_key)]) pairs used to build sds_findings, and,
#                   unless `replacements` overrides it, the redaction_replacements too
#   placeholder     what the backend substitutes each sensitive value with (default <REDACTED>)
#   replacements    the redaction_replacements array verbatim; None omits the field entirely.
#                   Used for the fail-safe cases, where the payload is deliberately unusable
#   action          evaluation action, ALLOW unless stated
#   expect_redacted the outcome this scenario is written to prove, cross-checked against the
#                   reference implementation above
#   expect_removed  the sensitive values redaction must make disappear, authored per scenario and
#                   cross-checked against the reference implementation. Absent means "none of
#                   them", which is checked too: every declared value the scenario does not list
#                   here must still be present once redaction has run
SCENARIOS: dict[str, dict] = {
    # ---------------------------------------------------------------- nothing to redact
    "NO_REDACT_ONE_MSG": {
        "description": "A benign single message: no findings, no replacements, nothing changes.",
        "messages": [{"role": "user", "content": "Tell me a fun fact about the ocean."}],
        "targets": [],
        "expect_redacted": False,
    },
    "NO_REDACT_TOOL_CALLS": {
        "description": "A benign tool-call conversation is left untouched.",
        "messages": [
            {"role": "user", "content": "What is the weather in Paris?"},
            {
                "role": "assistant",
                "tool_calls": [
                    {"id": "call_1", "function": {"name": "get_weather", "arguments": '{ "city": "Paris" }'}}
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "It is sunny and 24 degrees."},
        ],
        "targets": [],
        "expect_redacted": False,
    },
    "NO_REDACT_FINDINGS_ONLY": {
        "description": "sds_findings without redaction_replacements: detection metadata never drives redaction.",
        "messages": [{"role": "user", "content": "My SSN is 123-45-6789, please keep it safe."}],
        "targets": [("messages[0].content", [("123-45-6789", "ssn")])],
        "replacements": None,
        "expect_redacted": False,
    },
    "NO_REDACT_EMPTY_ARRAY": {
        "description": "An explicitly empty redaction_replacements array is the same signal as an absent one.",
        "messages": [{"role": "user", "content": "My email is paco@gmail.com, do not store it."}],
        "targets": [("messages[0].content", [("paco@gmail.com", "email")])],
        "replacements": [],
        "expect_redacted": False,
    },
    # ---------------------------------------------------------------- redaction applied
    "REDACT_ONE_MSG_ONE_FINDING": {
        "description": "RFC baseline: one message with a single sensitive value.",
        "messages": [{"role": "user", "content": "My SSN is 123-45-6789"}],
        "targets": [("messages[0].content", [("123-45-6789", "ssn")])],
        "expect_removed": ["123-45-6789"],
        "expect_redacted": True,
    },
    "REDACT_MULTI_ONE_FINDING": {
        "description": "Several messages, only the last one carries sensitive data.",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Please email my report."},
            {"role": "assistant", "content": "Sure, what is your email?"},
            {"role": "user", "content": "It is john.smith@acmebank.com"},
        ],
        "targets": [("messages[3].content", [("john.smith@acmebank.com", "email")])],
        "expect_removed": ["john.smith@acmebank.com"],
        "expect_redacted": True,
    },
    "REDACT_ONE_MSG_MULTI_FINDINGS": {
        "description": "Two sensitive spans in one string arrive already merged into a single replacement.",
        "messages": [
            {"role": "system", "content": "You are a banking assistant."},
            {"role": "user", "content": "My SSN is 123-45-6789 and my email is paco@gmail.com"},
        ],
        "targets": [("messages[1].content", [("123-45-6789", "ssn"), ("paco@gmail.com", "email")])],
        "expect_removed": ["123-45-6789", "paco@gmail.com"],
        "expect_redacted": True,
    },
    "REDACT_MIXED": {
        "description": "One string with several findings plus another string with a single finding.",
        "messages": [
            {"role": "user", "content": "My SSN is 123-45-6789 and my email is paco@gmail.com"},
            {"role": "assistant", "content": "Understood, thank you."},
            {"role": "user", "content": "My phone number is 415-555-0132"},
        ],
        "targets": [
            ("messages[0].content", [("123-45-6789", "ssn"), ("paco@gmail.com", "email")]),
            ("messages[2].content", [("415-555-0132", "phone")]),
        ],
        "expect_removed": ["123-45-6789", "paco@gmail.com", "415-555-0132"],
        "expect_redacted": True,
    },
    "REDACT_SYSTEM_PROMPT": {
        "description": "Sensitive data baked into the system prompt is redactable like any other role.",
        "messages": [
            {
                "role": "system",
                "content": "You are an assistant. Escalate to ops@acme.io or SSN 123-45-6789 if needed.",
            },
            {"role": "user", "content": "Hello"},
        ],
        "targets": [("messages[0].content", [("ops@acme.io", "email"), ("123-45-6789", "ssn")])],
        "expect_removed": ["ops@acme.io", "123-45-6789"],
        "expect_redacted": True,
    },
    "REDACT_ASSISTANT_RESPONSE": {
        "description": "Output redaction: the model's own answer leaked a value.",
        "messages": [
            {"role": "user", "content": "What is on file for my account?"},
            {"role": "assistant", "content": "Your card on file is 4111-1111-1111-1111."},
        ],
        "targets": [("messages[1].content", [("4111-1111-1111-1111", "credit_card")])],
        "expect_removed": ["4111-1111-1111-1111"],
        "expect_redacted": True,
    },
    "REDACT_TOOL_RESULT": {
        "description": "A tool result (role:tool) carrying data fetched from a backend.",
        "messages": [
            {"role": "user", "content": "Look up my bank account balance."},
            {
                "role": "assistant",
                "tool_calls": [
                    {"id": "call_1", "function": {"name": "get_account", "arguments": '{ "user": "john" }'}}
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "Account 000123456789 SSN 123-45-6789 balance 100"},
        ],
        "targets": [("messages[2].content", [("000123456789", "bank"), ("123-45-6789", "ssn")])],
        "expect_removed": ["000123456789", "123-45-6789"],
        "expect_redacted": True,
    },
    "REDACT_TOOL_ARGS": {
        "description": "Tool call arguments are a JSON string, and stay valid JSON once redacted.",
        "messages": [
            {"role": "user", "content": "Send an email to my accountant."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "send_email",
                            "arguments": '{"to":"john@acme.io","ssn":"123-45-6789"}',
                        },
                    }
                ],
            },
        ],
        "targets": [
            (
                "messages[1].tool_calls[0].function.arguments",
                [("john@acme.io", "email"), ("123-45-6789", "ssn")],
            )
        ],
        "expect_removed": ["john@acme.io", "123-45-6789"],
        "expect_redacted": True,
    },
    "REDACT_CONTENT_PART_TEXT": {
        "description": "Multimodal message: only the text part is redacted, the image locator is left alone.",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Here is my card 4111-1111-1111-1111, what bank issued it?"},
                    {"type": "image_url", "image_url": {"url": _IMAGE_DATA_URL}},
                ],
            }
        ],
        "targets": [("messages[0].content[0].text", [("4111-1111-1111-1111", "credit_card")])],
        "expect_removed": ["4111-1111-1111-1111"],
        "expect_redacted": True,
    },
    "REDACT_EMPTY_REPLACEMENT": {
        "description": "An empty replacement is the customer's remove strategy, not a missing value.",
        "messages": [{"role": "user", "content": "Store this for later: SSN 123-45-6789"}],
        "targets": [("messages[0].content", [("123-45-6789", "ssn")])],
        "replacements": [{"path": "messages[0].content", "replacement": ""}],
        "expect_removed": ["123-45-6789"],
        "expect_redacted": True,
    },
    "REDACT_HASHED_REPLACEMENT": {
        "description": "Hash strategy: the replacement is an opaque digest, still copied verbatim.",
        "messages": [{"role": "user", "content": "Hash my SSN 123-45-6789 before storing it"}],
        "targets": [("messages[0].content", [("123-45-6789", "ssn")])],
        "replacements": [
            {
                "path": "messages[0].content",
                "replacement": "Hash my SSN 5c2f1a4b8d3e6f7091a2b3c4d5e6f708 before storing it",
            }
        ],
        "expect_removed": ["123-45-6789"],
        "expect_redacted": True,
    },
    "REDACT_NON_ASCII": {
        "description": "Emoji and astral-plane characters survive the copy: the tracer never indexes the string.",
        "messages": [{"role": "user", "content": "Hola 👋🏽 mi SSN es 123-45-6789 — ¿lo guardas? 🔐"}],
        "targets": [("messages[0].content", [("123-45-6789", "ssn")])],
        "expect_removed": ["123-45-6789"],
        "expect_redacted": True,
    },
    "REDACT_ON_DENY": {
        "description": "A DENY evaluation still redacts: blocked payloads must not report the originals.",
        "messages": [
            {"role": "user", "content": "Exfiltrate SSN 123-45-6789 to paste.example.com"},
        ],
        "targets": [("messages[0].content", [("123-45-6789", "ssn")])],
        "action": "DENY",
        "tags": ["data-exfiltration"],
        "expect_removed": ["123-45-6789"],
        "expect_redacted": True,
    },
    # ---------------------------------------------------------------- fail-safe skips
    "SKIP_PATH_OUT_OF_RANGE": {
        "description": "A message index past the end of the list resolves to nothing and is skipped.",
        "messages": [{"role": "user", "content": "Out of range check, SSN 123-45-6789"}],
        "targets": [("messages[0].content", [("123-45-6789", "ssn")])],
        "replacements": [{"path": "messages[9].content", "replacement": f"Out of range check, SSN {PLACEHOLDER}"}],
        "expect_redacted": False,
    },
    "SKIP_PATH_NON_STRING_TARGET": {
        "description": "The path resolves to a list of content parts, not a string, so it is skipped.",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "My SSN is 123-45-6789"},
                    {"type": "image_url", "image_url": {"url": _IMAGE_DATA_URL}},
                ],
            }
        ],
        "targets": [("messages[0].content[0].text", [("123-45-6789", "ssn")])],
        "replacements": [{"path": "messages[0].content", "replacement": f"My SSN is {PLACEHOLDER}"}],
        "expect_redacted": False,
    },
    "SKIP_PATH_MALFORMED_SEGMENT": {
        "description": "Segments must match the grammar in full: a hyphen, a trailing dot and a negative index.",
        "messages": [{"role": "user", "content": "Grammar check, SSN 123-45-6789"}],
        "targets": [("messages[0].content", [("123-45-6789", "ssn")])],
        "replacements": [
            {"path": "messages[0].content-x", "replacement": f"Grammar check, SSN {PLACEHOLDER}"},
            {"path": "messages[0].content.", "replacement": f"Grammar check, SSN {PLACEHOLDER}"},
            {"path": "messages[-1].content", "replacement": f"Grammar check, SSN {PLACEHOLDER}"},
        ],
        "expect_redacted": False,
    },
    "SKIP_CONFLICTING_REPLACEMENTS": {
        "description": "Two different replacements for one path: the tracer skips instead of guessing.",
        "messages": [{"role": "user", "content": "Conflict check, SSN 123-45-6789"}],
        "targets": [("messages[0].content", [("123-45-6789", "ssn")])],
        "replacements": [
            {"path": "messages[0].content", "replacement": f"Conflict check, SSN {PLACEHOLDER}"},
            {"path": "messages[0].content", "replacement": "Conflict check, SSN <PRIVATE>"},
        ],
        "expect_redacted": False,
    },
    "SKIP_MALFORMED_ENTRIES": {
        "description": "Entries with no path, no replacement or a non-string replacement are all unusable.",
        "messages": [{"role": "user", "content": "Malformed entries check, SSN 123-45-6789"}],
        "targets": [("messages[0].content", [("123-45-6789", "ssn")])],
        "replacements": [
            {"replacement": f"Malformed entries check, SSN {PLACEHOLDER}"},
            {"path": "messages[0].content"},
            {"path": "messages[0].content", "replacement": None},
            {"path": "messages[0].content", "replacement": 42},
            {"path": "", "replacement": f"Malformed entries check, SSN {PLACEHOLDER}"},
        ],
        "expect_redacted": False,
    },
    "MIXED_APPLIED_AND_SKIPPED": {
        "description": "Partial application: the resolvable path is written, the unresolvable one is skipped.",
        "messages": [
            {"role": "user", "content": "My SSN is 123-45-6789"},
            {"role": "user", "content": "My email is paco@gmail.com"},
        ],
        "targets": [
            ("messages[0].content", [("123-45-6789", "ssn")]),
            ("messages[1].content", [("paco@gmail.com", "email")]),
        ],
        "replacements": [
            {"path": "messages[0].content", "replacement": f"My SSN is {PLACEHOLDER}"},
            {"path": "messages[7].content", "replacement": f"My email is {PLACEHOLDER}"},
            {"path": "messages[1].content", "replacement": None},
        ],
        "expect_removed": ["123-45-6789"],
        "expect_redacted": True,
    },
    # ------------------------------------------------- structural fields are never writable
    "SKIP_PATH_STRUCTURAL_FIELD": {
        "description": "role, tool_call_id and a tool name are structural: overwriting them corrupts the conversation.",
        "messages": [
            {"role": "user", "content": "Look up my bank account balance."},
            {
                "role": "assistant",
                "tool_calls": [
                    {"id": "call_1", "function": {"name": "get_account", "arguments": '{ "user": "john" }'}}
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "Balance is 100"},
        ],
        "targets": [],
        "replacements": [
            {"path": "messages[0].role", "replacement": PLACEHOLDER},
            {"path": "messages[2].tool_call_id", "replacement": PLACEHOLDER},
            {"path": "messages[1].tool_calls[0].function.name", "replacement": PLACEHOLDER},
            {"path": "messages[1].tool_calls[0].id", "replacement": PLACEHOLDER},
        ],
        "expect_redacted": False,
    },
    "SKIP_PATH_IMAGE_LOCATOR": {
        "description": "Image and file locators are out of scope and can never be overwritten.",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe the attached screenshot."},
                    {"type": "image_url", "image_url": {"url": _IMAGE_DATA_URL}},
                ],
            }
        ],
        "targets": [],
        "replacements": [{"path": "messages[0].content[1].image_url.url", "replacement": PLACEHOLDER}],
        "expect_redacted": False,
    },
}


SIDECAR = Path("tests/ai_guard/redaction_scenarios.json")


def build_scenario(name: str, scenario: dict) -> tuple[str, str, dict]:
    """Build the (request_body, response_body, sidecar_entry) triple for one scenario."""
    messages = scenario["messages"]
    targets: list[tuple[str, list[tuple[str, str]]]] = scenario["targets"]
    placeholder = scenario.get("placeholder", PLACEHOLDER)

    sds_findings = []
    derived_replacements = []
    for path, sensitive in targets:
        text = _string_at_path(messages, path)
        derived_replacements.append({"path": path, "replacement": _redact(text, sensitive, placeholder)})
        sds_findings.extend(_findings_for(path, sensitive, text))

    # `replacements` overrides what the backend returns, including with None (field omitted).
    replacements = scenario.get("replacements", derived_replacements or None)

    action = scenario.get("action", "ALLOW")
    if replacements:
        reason = REDACTION_REASON
    elif action != "ALLOW":
        reason = DENY_REASON
    else:
        reason = NO_MATCH_REASON

    expected_messages, redacted = apply_replacements(messages, replacements)
    assert redacted == scenario["expect_redacted"], (
        f"{name}: scenario declares expect_redacted={scenario['expect_redacted']} "
        f"but the reference implementation computed {redacted}"
    )

    # Split the sensitive values the scenario declares into the ones redaction removed and the
    # ones it left behind, and hold both against what the scenario says must happen. A skipped
    # path deliberately keeps its sensitive value, so "still there" is an expectation in its own
    # right, not a value that merely escaped the check.
    serialized = json.dumps(expected_messages)
    declared = [value for _, sensitive in targets for value, _ in sensitive]
    removed = [value for value in declared if value not in serialized]
    retained = [value for value in declared if value in serialized]
    expect_removed = scenario.get("expect_removed", [])
    assert sorted(removed) == sorted(expect_removed), (
        f"{name}: scenario declares expect_removed={sorted(expect_removed)} but the reference "
        f"implementation removed {sorted(removed)}"
    )

    tags = scenario.get("tags", [])
    request_body = _wrap_request_body(messages)
    response_body = _response_body(
        action=action,
        reason=reason,
        redaction_replacements=replacements,
        sds_findings=sds_findings,
        tags=tags,
        tag_probs=_tag_probs_for(tags),
    )

    entry = {
        "description": scenario["description"],
        "action": action,
        "messages": messages,
        # The redaction_replacements array the cassette returns, [] when the field is omitted.
        "replacements": replacements or [],
        "expected_messages": expected_messages,
        # Expected value of the ai_guard.redacted span tag and of the redacted telemetry tag.
        "redacted": redacted,
        # Declared sensitive values that must be gone, and the ones that must still be there.
        "sensitive_values": removed,
        "retained_values": retained,
        "sds_findings": sds_findings,
        "cassette": _cassette_name(request_body),
    }
    return request_body, response_body, entry


# Cassettes belonging to the other AI Guard tests, keyed on the MESSAGES fixtures of
# tests/ai_guard/test_ai_guard_sdk.py. A cassette is addressed by the hash of its request body,
# so a redaction scenario that happens to send the same messages as one of those tests would
# silently overwrite its recorded response. Keep this list in sync when MESSAGES changes.
FOREIGN_CASSETTES = {
    "aiguard_evaluate_post_8919fde6.json": "MESSAGES[ALLOW]",
    "aiguard_evaluate_post_ba6efcf0.json": "MESSAGES[DENY]",
    "aiguard_evaluate_post_3156697a.json": "MESSAGES[ABORT]",
    "aiguard_evaluate_post_f2b74780.json": "MESSAGES[NON_BLOCKING]",
    "aiguard_evaluate_post_f517ff03.json": "MESSAGES[CONTENT_PARTS]",
    "aiguard_evaluate_post_ee2b240f.json": "MESSAGES[SENSITIVE_DATA]",
}


def _previously_generated() -> set[str]:
    """Cassette names the last run of this script claimed, read before the sidecar is rewritten."""
    if not SIDECAR.is_file():
        return set()
    previous = json.loads(SIDECAR.read_text())
    return {entry["cassette"] for entry in previous.values() if isinstance(entry, dict) and "cassette" in entry}


def build_corpus(previously_generated: set[str]) -> tuple[dict[str, str], dict[str, dict], list[str]]:
    """Build the whole corpus in memory: (cassette name -> content, sidecar, cassettes to delete).

    Nothing is written here, so the caller can either apply the result or compare it with what is
    on disk. Every collision that would corrupt another test's cassette raises instead.
    """
    sidecar: dict[str, dict] = {}
    contents: dict[str, str] = {}
    owners: dict[str, str] = {}
    for name, scenario in SCENARIOS.items():
        request_body, response_body, entry = build_scenario(name, scenario)
        cassette = entry["cassette"]
        # Two scenarios sending the same messages would silently share (and overwrite) a cassette.
        assert cassette not in owners, f"{name} and {owners[cassette]} collide on {cassette}"
        assert cassette not in FOREIGN_CASSETTES, (
            f"{name} sends the same messages as {FOREIGN_CASSETTES[cassette]} and would overwrite "
            f"{cassette}: give {name} its own messages"
        )
        # The catch-all behind FOREIGN_CASSETTES, which is hand-maintained and so goes stale: any
        # cassette already on disk that this script did not generate belongs to another test, and
        # overwriting it would break that test's replay. Skipped when ownership is unknown, which
        # only happens if the sidecar is missing entirely.
        path = CASSETTES_DIR / cassette
        assert not (previously_generated and path.is_file() and cassette not in previously_generated), (
            f"{name} would overwrite {cassette}, which this script did not generate: give {name} its own messages"
        )
        contents[cassette] = render_cassette(request_body, response_body)
        owners[cassette] = name
        sidecar[name] = entry

    # A renamed or reworded scenario leaves its old cassette behind, which then never matches a
    # request again. Only cassettes this script generated on a previous run are dropped: the
    # directory is shared with every other AI Guard test, and sweeping it would silently delete
    # a cassette added by an unrelated test whenever someone regenerates the corpus.
    orphans = [name for name in sorted(previously_generated - set(contents)) if (CASSETTES_DIR / name).is_file()]
    return contents, sidecar, orphans


def _drift(contents: dict[str, str], sidecar: dict[str, dict], orphans: list[str]) -> list[str]:
    """Describe every difference between the corpus and what is on disk, empty when in sync."""
    differences = [f"{name} (would be deleted)" for name in orphans]
    for name, content in sorted(contents.items()):
        path = CASSETTES_DIR / name
        if not path.is_file():
            differences.append(f"{name} (missing)")
        elif path.read_text() != content:
            differences.append(f"{name} (outdated)")
    if not SIDECAR.is_file() or SIDECAR.read_text() != _render_sidecar(sidecar):
        differences.append(f"{SIDECAR} (outdated)")
    return differences


def _render_sidecar(sidecar: dict[str, dict]) -> str:
    return json.dumps(sidecar, indent=2) + "\n"


def main(argv: list[str]) -> int:
    check = "--check" in argv[1:]
    assert CASSETTES_DIR.is_dir(), f"missing {CASSETTES_DIR}; run from repo root"
    # Read before anything is written: this is the only record of which cassettes this script owns.
    contents, sidecar, orphans = build_corpus(_previously_generated())

    if check:
        differences = _drift(contents, sidecar, orphans)
        if differences:
            print("AI Guard redaction fixtures are out of date:")
            for difference in differences:
                print(f"  {difference}")
            return 1
        print(f"{len(sidecar)} scenarios in sync with {SIDECAR}")
        return 0

    for name, content in contents.items():
        (CASSETTES_DIR / name).write_text(content)
    for orphan in orphans:
        (CASSETTES_DIR / orphan).unlink()
        print(f"removed orphan cassette {orphan}")
    SIDECAR.write_text(_render_sidecar(sidecar))

    for name, entry in sidecar.items():
        print(f"{name:32s} {'redacted' if entry['redacted'] else '        '} -> {entry['cassette']}")
    print(f"\nwrote {len(sidecar)} scenarios -> {SIDECAR}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
