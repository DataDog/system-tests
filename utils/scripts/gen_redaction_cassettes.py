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

Run from the repo root:  python3 utils/scripts/gen_redaction_cassettes.py
"""

from __future__ import annotations

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
}


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


def _redact(text: str, sensitive: list[tuple[str, str]]) -> str:
    redacted = text
    for value, _ in sensitive:
        redacted = redacted.replace(value, PLACEHOLDER)
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


def _response_body(*, action: str, reason: str, redaction_replacements: list, sds_findings: list) -> str:
    attributes = {
        "action": action,
        "is_blocking_enabled": True,
        "reason": reason,
    }
    if redaction_replacements:
        attributes["redaction_replacements"] = redaction_replacements
    attributes["sds_findings"] = sds_findings
    attributes["tag_probs"] = dict(_BENIGN_TAG_PROBS)
    attributes["tags"] = []
    return json.dumps({"data": {"id": "redaction-fixture", "type": "evaluations", "attributes": attributes}})


def build_cassette(messages: list, *, targets: list[tuple[str, list[tuple[str, str]]]], reason: str) -> tuple[str, str]:
    """targets: list of (path, [(sensitive_value, rule_key), ...]) for each string that must be redacted."""
    request_body = _wrap_request_body(messages)

    redaction_replacements = []
    sds_findings = []
    for path, sensitive in targets:
        text = _string_at_path(messages, path)
        redaction_replacements.append({"path": path, "replacement": _redact(text, sensitive)})
        sds_findings.extend(_findings_for(path, sensitive, text))

    if redaction_replacements:
        action, r = "ALLOW", reason
    else:
        action, r = "ALLOW", "No rule match."

    response_body = _response_body(
        action=action, reason=r, redaction_replacements=redaction_replacements, sds_findings=sds_findings
    )
    return request_body, response_body


def _string_at_path(messages: list, path: str) -> str:
    """Minimal resolver for the paths used in the fixtures (mirrors the RFC path grammar)."""
    segment_re = re.compile(r"^(?P<name>[A-Za-z0-9_]+)(?:\[(?P<index>[0-9]+)\])?$")
    obj: object = {"messages": messages}
    for segment in path.split("."):
        m = segment_re.match(segment)
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

# Each scenario mirrors the MESSAGES fixtures in tests/ai_guard/test_ai_guard_sdk.py.
SCENARIOS: dict[str, dict] = {
    # 1. one message, no sensitive data -> no redaction (control)
    "NO_REDACT_ONE_MSG": {
        "messages": [{"role": "user", "content": "Tell me a fun fact about the ocean."}],
        "targets": [],
    },
    # 2. one message with a single sensitive value to redact
    "REDACT_ONE_MSG_ONE_FINDING": {
        "messages": [{"role": "user", "content": "My SSN is 123-45-6789"}],
        "targets": [("messages[0].content", [("123-45-6789", "ssn")])],
    },
    # 3. multiple messages, only one needs redaction
    "REDACT_MULTI_ONE_FINDING": {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Please email my report."},
            {"role": "assistant", "content": "Sure, what is your email?"},
            {"role": "user", "content": "It is john.smith@acmebank.com"},
        ],
        "targets": [("messages[3].content", [("john.smith@acmebank.com", "email")])],
    },
    # 4. multiple messages, one message with multiple findings in a single string
    "REDACT_ONE_MSG_MULTI_FINDINGS": {
        "messages": [
            {"role": "system", "content": "You are a banking assistant."},
            {"role": "user", "content": "My SSN is 123-45-6789 and my email is paco@gmail.com"},
        ],
        "targets": [("messages[1].content", [("123-45-6789", "ssn"), ("paco@gmail.com", "email")])],
    },
    # 5. multiple messages: one string with multiple findings and another with a single finding
    "REDACT_MIXED": {
        "messages": [
            {"role": "user", "content": "My SSN is 123-45-6789 and my email is paco@gmail.com"},
            {"role": "assistant", "content": "Understood, thank you."},
            {"role": "user", "content": "My phone number is 415-555-0132"},
        ],
        "targets": [
            ("messages[0].content", [("123-45-6789", "ssn"), ("paco@gmail.com", "email")]),
            ("messages[2].content", [("415-555-0132", "phone")]),
        ],
    },
    # 6. tool calls with an insecure tool result (role:tool content carries sensitive data)
    "REDACT_TOOL_RESULT": {
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
    },
    # 7. tool calls that are benign -> no redaction (control)
    "NO_REDACT_TOOL_CALLS": {
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
    },
    # 8. tool call arguments carry sensitive data -> redact the arguments JSON string
    "REDACT_TOOL_ARGS": {
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
    },
    # 9. insecure system prompt (sensitive data baked into the system message)
    "REDACT_SYSTEM_PROMPT": {
        "messages": [
            {
                "role": "system",
                "content": "You are an assistant. Escalate to ops@acme.io or SSN 123-45-6789 if needed.",
            },
            {"role": "user", "content": "Hello"},
        ],
        "targets": [("messages[0].content", [("ops@acme.io", "email"), ("123-45-6789", "ssn")])],
    },
}


SIDECAR = Path("tests/ai_guard/redaction_scenarios.json")


def main() -> None:
    assert CASSETTES_DIR.is_dir(), f"missing {CASSETTES_DIR}; run from repo root"
    sidecar: dict[str, dict] = {}
    for name, scenario in SCENARIOS.items():
        request_body, response_body = build_cassette(
            scenario["messages"], targets=scenario["targets"], reason=REDACTION_REASON
        )
        cassette = write_cassette(request_body, response_body)
        print(f"{name:32s} -> {cassette}")

        redactions = []
        for path, sensitive in scenario["targets"]:
            text = _string_at_path(scenario["messages"], path)
            redactions.append(
                {
                    "path": path,
                    "replacement": _redact(text, sensitive),
                    "sensitive_values": [value for value, _ in sensitive],
                }
            )
        sidecar[name] = {"messages": scenario["messages"], "redactions": redactions}

    SIDECAR.write_text(json.dumps(sidecar, indent=2) + "\n")
    print(f"\nwrote scenario sidecar -> {SIDECAR}")


if __name__ == "__main__":
    main()
