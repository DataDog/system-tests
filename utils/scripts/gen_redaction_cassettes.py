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
sensitive values that must be gone, and whether the tracer must report the
evaluation as redacted (the ai_guard.redacted span tag and the redacted telemetry
tag). Those expectations come from apply_replacements below, a reference
implementation of the RFC algorithm, cross-checked against the intent each
scenario declares in expect_redacted.

Run from the repo root:  python3 utils/scripts/gen_redaction_cassettes.py
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
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
# The whole segment must match, a partial match is rejected.
SEGMENT_RE = re.compile(r"^(?P<name>[A-Za-z0-9_]+)(?:\[(?P<index>[0-9]+)\])?$")

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
        match = SEGMENT_RE.match(raw)
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
    """Build sds_findings for the (value, rule_key) pairs found in `text` at `path`."""
    findings = []
    for value, rule_key in sensitive:
        display, tag, category = RULES[rule_key]
        start = text.index(value)
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
    return findings


def _redact(text: str, sensitive: list[tuple[str, str]], placeholder: str) -> str:
    redacted = text
    for value, _ in sensitive:
        redacted = redacted.replace(value, placeholder)
    return redacted


# Benign tag probabilities: redaction scenarios are ALLOW with no attack category matched.
# tag_probs is part of the real evaluation response, so we keep it for deserializer parity.
_BENIGN_TAG_PROBS = {
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
        m = SEGMENT_RE.match(segment)
        assert m, f"bad segment {segment!r}"
        obj = obj[m.group("name")]  # type: ignore[index]
        if m.group("index") is not None:
            obj = obj[int(m.group("index"))]  # type: ignore[index]
    assert isinstance(obj, str), f"path {path} did not resolve to a string"
    return obj


def write_cassette(request_body: str, response_body: str) -> str:
    name = _cassette_name(request_body)
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
    path = CASSETTES_DIR / name
    path.write_text(json.dumps(cassette, indent=1) + "\n")
    return name


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
        "expect_redacted": True,
    },
    "REDACT_ONE_MSG_MULTI_FINDINGS": {
        "description": "Two sensitive spans in one string arrive already merged into a single replacement.",
        "messages": [
            {"role": "system", "content": "You are a banking assistant."},
            {"role": "user", "content": "My SSN is 123-45-6789 and my email is paco@gmail.com"},
        ],
        "targets": [("messages[1].content", [("123-45-6789", "ssn"), ("paco@gmail.com", "email")])],
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
        "expect_redacted": True,
    },
    "REDACT_ASSISTANT_RESPONSE": {
        "description": "Output redaction: the model's own answer leaked a value.",
        "messages": [
            {"role": "user", "content": "What is on file for my account?"},
            {"role": "assistant", "content": "Your card on file is 4111-1111-1111-1111."},
        ],
        "targets": [("messages[1].content", [("4111-1111-1111-1111", "credit_card")])],
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
        "expect_redacted": True,
    },
    "REDACT_EMPTY_REPLACEMENT": {
        "description": "An empty replacement is the customer's remove strategy, not a missing value.",
        "messages": [{"role": "user", "content": "Store this for later: SSN 123-45-6789"}],
        "targets": [("messages[0].content", [("123-45-6789", "ssn")])],
        "replacements": [{"path": "messages[0].content", "replacement": ""}],
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
        "expect_redacted": True,
    },
    "REDACT_NON_ASCII": {
        "description": "Emoji and astral-plane characters survive the copy: the tracer never indexes the string.",
        "messages": [{"role": "user", "content": "Hola 👋🏽 mi SSN es 123-45-6789 — ¿lo guardas? 🔐"}],
        "targets": [("messages[0].content", [("123-45-6789", "ssn")])],
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

    # Only the values redaction actually removed can be asserted absent: a skipped path
    # deliberately leaves its sensitive value in place.
    serialized = json.dumps(expected_messages)
    removed = [value for _, sensitive in targets for value, _ in sensitive if value not in serialized]

    request_body = _wrap_request_body(messages)
    response_body = _response_body(
        action=action,
        reason=reason,
        redaction_replacements=replacements,
        sds_findings=sds_findings,
        tags=scenario.get("tags", []),
        tag_probs=dict(_BENIGN_TAG_PROBS),
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
        "sensitive_values": removed,
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


def main() -> None:
    assert CASSETTES_DIR.is_dir(), f"missing {CASSETTES_DIR}; run from repo root"
    sidecar: dict[str, dict] = {}
    cassettes: dict[str, str] = {}
    for name, scenario in SCENARIOS.items():
        request_body, response_body, entry = build_scenario(name, scenario)
        cassette = entry["cassette"]
        # Two scenarios sending the same messages would silently share (and overwrite) a cassette.
        assert cassette not in cassettes, f"{name} and {cassettes[cassette]} collide on {cassette}"
        assert cassette not in FOREIGN_CASSETTES, (
            f"{name} sends the same messages as {FOREIGN_CASSETTES[cassette]} and would overwrite "
            f"{cassette}: give {name} its own messages"
        )
        write_cassette(request_body, response_body)
        cassettes[cassette] = name
        sidecar[name] = entry
        print(f"{name:32s} {'redacted' if entry['redacted'] else '        '} -> {cassette}")

    # A renamed or reworded scenario leaves its old cassette behind, which then never matches
    # a request again. Drop anything in the directory that no test claims.
    for existing in sorted(CASSETTES_DIR.glob("*.json")):
        if existing.name not in cassettes and existing.name not in FOREIGN_CASSETTES:
            existing.unlink()
            print(f"removed orphan cassette {existing.name}")

    SIDECAR.write_text(json.dumps(sidecar, indent=2) + "\n")
    print(f"\nwrote {len(sidecar)} scenarios -> {SIDECAR}")


if __name__ == "__main__":
    main()
