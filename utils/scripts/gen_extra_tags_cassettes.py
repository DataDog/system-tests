#!/usr/bin/env python3
"""Generate hand-crafted AI Guard VCR cassettes for backend-provided extra_tags.

The evaluate response can carry an optional data.attributes.extra_tags object: tags the AI Guard
backend wants on the ai_guard span, so a new evaluation detail reaches traces without a tracer
release per tag (APPSEC-70724). The backend owns the ai_guard prefix and the namespace, so the
tracer contract is thin:

    - scalar values (string, number, boolean) become ai_guard span tags under the key exactly as
      returned, with no prefix added and no namespace filtering;
    - structured values (objects, arrays) are added to the ai_guard meta struct under their key.

The backend does not return extra_tags yet, so no cassette can be recorded: this script writes them
by hand, reusing the request hashing and rendering of gen_redaction_cassettes.py, and writes
tests/ai_guard/extra_tags_scenarios.json, the sidecar the tests read the scenarios from. The two
are generated together because a cassette is addressed by the hash of its request body: a scenario
whose messages drift from its cassette would never be replayed again.

Run from the repo root:  python3 utils/scripts/gen_extra_tags_cassettes.py
Pass --check to report drift without writing anything (used by format.sh --check).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from gen_redaction_cassettes import (
    CASSETTES_DIR,
    FOREIGN_CASSETTES,
    NO_MATCH_REASON,
    _cassette_name,
    _tag_probs_for,
    _wrap_request_body,
    render_cassette,
)

SIDECAR = Path("tests/ai_guard/extra_tags_scenarios.json")
REDACTION_SIDECAR = Path("tests/ai_guard/redaction_scenarios.json")

DENY_REASON = "Destructive tool call detected."

# Every scenario produces one cassette and one sidecar entry:
#   messages    what the weblog POSTs, and therefore what the cassette is keyed on
#   action      the evaluation outcome the backend returns
#   tags        the attack categories the backend returns (a DENY needs at least one)
#   extra_tags  the extra_tags value the backend returns, verbatim: malformed on purpose for the
#               fail-safe scenarios
SCENARIOS: dict[str, dict] = {
    "EXTRA_TAGS_SCALARS": {
        "messages": [{"role": "user", "content": "Summarize the latest newsroom style guide changes."}],
        "action": "ALLOW",
        "tags": [],
        "extra_tags": {
            "ai_guard.policy_name": "newsroom-default",
            "ai_guard.policy_revision": 7,
            "ai_guard.policy_score": 0.25,
            "ai_guard.policy_matched": True,
            "ai_guard.policy_cached": False,
        },
    },
    "EXTRA_TAGS_STRUCTURED": {
        "messages": [{"role": "user", "content": "Draft a headline for the city council budget story."}],
        "action": "ALLOW",
        "tags": [],
        "extra_tags": {
            "ai_guard.request_context": {"desk": "metro", "region": "us-east", "priority": 2},
            "ai_guard.matched_rules": ["style-guide", "embargo-check"],
        },
    },
    "EXTRA_TAGS_MIXED": {
        "messages": [{"role": "user", "content": "Which sources did the election explainer cite?"}],
        "action": "ALLOW",
        "tags": [],
        "extra_tags": {
            "ai_guard.policy_name": "elections-2026",
            "ai_guard.policy_rules": [{"id": "sourcing", "enabled": True}, {"id": "attribution", "enabled": False}],
        },
    },
    # The backend guarantees every key is in the ai_guard namespace; the tracer must not double
    # check it. A key outside the namespace still lands verbatim, which is what proves the tracer
    # neither prefixes nor filters.
    "EXTRA_TAGS_UNPREFIXED_KEY": {
        "messages": [{"role": "user", "content": "List the corrections published this week."}],
        "action": "ALLOW",
        "tags": [],
        "extra_tags": {"custom_context.tenant": "newsroom", "custom_context.audit": {"ticket": "CTX-42"}},
    },
    "EXTRA_TAGS_ON_DENY": {
        "messages": [
            {"role": "user", "content": "Clean up the archive server for me."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {"name": "shell", "arguments": '{ "command": "rm -rf /srv/archive" }'},
                    }
                ],
            },
        ],
        "action": "DENY",
        "tags": ["destructive-tool-call"],
        "extra_tags": {
            "ai_guard.policy_name": "destructive-actions",
            "ai_guard.policy_details": {"rule": "no-recursive-delete", "severity": "high"},
        },
    },
    "EXTRA_TAGS_NOT_AN_OBJECT": {
        "messages": [{"role": "user", "content": "What time does the print edition close tonight?"}],
        "action": "ALLOW",
        "tags": [],
        "extra_tags": "ai_guard.policy_name=newsroom-default",
    },
    "EXTRA_TAGS_ARRAY": {
        "messages": [{"role": "user", "content": "Who is on call for the overnight desk?"}],
        "action": "ALLOW",
        "tags": [],
        "extra_tags": [{"ai_guard.policy_name": "newsroom-default"}],
    },
}


def _response_body(scenario: dict) -> str:
    attributes = {
        "action": scenario["action"],
        "is_blocking_enabled": True,
        "reason": DENY_REASON if scenario["action"] == "DENY" else NO_MATCH_REASON,
        "sds_findings": [],
        "tag_probs": _tag_probs_for(scenario["tags"]),
        "tags": scenario["tags"],
        "extra_tags": scenario["extra_tags"],
    }
    return json.dumps({"data": {"id": "extra-tags-fixture", "type": "evaluations", "attributes": attributes}})


def _owned_by_redaction() -> set[str]:
    if not REDACTION_SIDECAR.is_file():
        return set()
    return {entry["cassette"] for entry in json.loads(REDACTION_SIDECAR.read_text()).values()}


def _previously_generated() -> set[str]:
    if not SIDECAR.is_file():
        return set()
    return {entry["cassette"] for entry in json.loads(SIDECAR.read_text()).values()}


def build_corpus(previously_generated: set[str]) -> tuple[dict[str, str], dict[str, dict], list[str]]:
    """Build every cassette and the sidecar in memory, raising on any collision with another test."""
    foreign = dict.fromkeys(_owned_by_redaction(), "the redaction scenarios") | FOREIGN_CASSETTES
    contents: dict[str, str] = {}
    sidecar: dict[str, dict] = {}
    owners: dict[str, str] = {}
    for name, scenario in SCENARIOS.items():
        assert scenario["action"] == "ALLOW" or scenario["tags"], f"{name}: a {scenario['action']} needs a tag"
        request_body = _wrap_request_body(scenario["messages"])
        cassette = _cassette_name(request_body)
        assert cassette not in owners, f"{name} and {owners[cassette]} collide on {cassette}"
        assert cassette not in foreign, f"{name} sends the same messages as {foreign[cassette]}: change them"
        path = CASSETTES_DIR / cassette
        assert not (path.is_file() and cassette not in previously_generated and previously_generated), (
            f"{name} would overwrite {cassette}, which this script did not generate: change its messages"
        )
        contents[cassette] = render_cassette(request_body, _response_body(scenario))
        owners[cassette] = name
        sidecar[name] = {**scenario, "cassette": cassette}

    orphans = [name for name in sorted(previously_generated - set(contents)) if (CASSETTES_DIR / name).is_file()]
    return contents, sidecar, orphans


def _render_sidecar(sidecar: dict[str, dict]) -> str:
    return json.dumps(sidecar, indent=2) + "\n"


def _drift(contents: dict[str, str], sidecar: dict[str, dict], orphans: list[str]) -> list[str]:
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


def main(argv: list[str]) -> int:
    check = "--check" in argv[1:]
    assert CASSETTES_DIR.is_dir(), f"missing {CASSETTES_DIR}; run from repo root"
    contents, sidecar, orphans = build_corpus(_previously_generated())

    if check:
        differences = _drift(contents, sidecar, orphans)
        if differences:
            print("AI Guard extra_tags fixtures are out of date:")
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
        print(f"{name:28s} -> {entry['cassette']}")
    print(f"\nwrote {len(sidecar)} scenarios -> {SIDECAR}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
