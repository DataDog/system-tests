#!/usr/bin/env python3
"""Generate hand-crafted AI Guard VCR cassettes for backend-provided extra_tags and extra_metastruct.

The evaluate response can carry two optional attributes so an AI Guard policy can enrich the
ai_guard span without a tracer release per tag (APPSEC-70724). Both are lists of {key, value}
objects rather than maps, because dotted keys such as ai_guard.evaluate_id are not valid JSON:API
member names:

    - extra_tags holds string values, each set as an ai_guard span tag under the key exactly as
      returned;
    - extra_metastruct holds any value (object, array or scalar), each added to the ai_guard meta
      struct under the key exactly as returned.

The backend owns the ai_guard prefix and the namespace, so tracers never add the prefix or filter
keys. The first entry the backend sends is the evaluation ID (the same value as data.id), as
ai_guard.evaluate_id in extra_tags and as evaluate_id in extra_metastruct. A malformed field or
entry is skipped and never changes the evaluation.

The backend does not return these attributes in the recorded cassettes, so this script writes them
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
import uuid
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

# Fixed namespace so every scenario gets a stable evaluation ID (data.id) across regenerations.
EVALUATION_ID_NAMESPACE = uuid.UUID("6f0e8c1a-3b9d-4c55-9a51-0c2f4e7d8b13")


def _evaluation_id(name: str) -> str:
    return str(uuid.uuid5(EVALUATION_ID_NAMESPACE, name))


def _kv(**entries: object) -> list[dict]:
    return [{"key": key, "value": value} for key, value in entries.items()]


def _evaluate_id_entries(name: str) -> tuple[list[dict], list[dict]]:
    evaluation_id = _evaluation_id(name)
    return (
        [{"key": "ai_guard.evaluate_id", "value": evaluation_id}],
        [{"key": "evaluate_id", "value": evaluation_id}],
    )


# Every scenario produces one cassette and one sidecar entry:
#   messages          what the weblog POSTs, and therefore what the cassette is keyed on
#   action            the evaluation outcome the backend returns
#   tags              the attack categories the backend returns (a DENY needs at least one)
#   extra_tags        the extra_tags value the backend returns, verbatim (omitted when absent)
#   extra_metastruct  the extra_metastruct value the backend returns, verbatim (omitted when absent)
#   expected_tags, expected_metastruct, skipped_tags
#                     what the tracer must apply, only spelled out for the fail-safe scenarios, whose
#                     payloads are malformed on purpose; for the others it is derived from the lists
SCENARIOS: dict[str, dict] = {
    "EXTRA_TAGS": {
        "messages": [{"role": "user", "content": "Summarize the latest newsroom style guide changes."}],
        "action": "ALLOW",
        "tags": [],
        "extra_tags": _kv(**{"ai_guard.policy_name": "newsroom-default", "ai_guard.policy_revision": "7"}),
    },
    "EXTRA_METASTRUCT": {
        "messages": [{"role": "user", "content": "Draft a headline for the city council budget story."}],
        "action": "ALLOW",
        "tags": [],
        "extra_metastruct": _kv(
            request_context={"desk": "metro", "region": "us-east", "priority": 2},
            matched_rules=["style-guide", "embargo-check"],
            policy_rules=[{"id": "sourcing", "enabled": True}, {"id": "attribution", "enabled": False}],
            policy_score=0.25,
            policy_name="newsroom-default",
        ),
    },
    "EVALUATE_ID": {
        "messages": [{"role": "user", "content": "Which sources did the election explainer cite?"}],
        "action": "ALLOW",
        "tags": [],
        "extra_tags": _evaluate_id_entries("EVALUATE_ID")[0] + _kv(**{"ai_guard.policy_name": "elections-2026"}),
        "extra_metastruct": _evaluate_id_entries("EVALUATE_ID")[1] + _kv(policy={"name": "elections-2026"}),
    },
    # The backend guarantees every extra_tags key is in the ai_guard namespace; the tracer must not
    # double check it. A key outside the namespace still lands verbatim, which is what proves the
    # tracer neither prefixes nor filters.
    "KEYS_VERBATIM": {
        "messages": [{"role": "user", "content": "List the corrections published this week."}],
        "action": "ALLOW",
        "tags": [],
        "extra_tags": _kv(**{"custom_context.tenant": "newsroom"}),
        "extra_metastruct": _kv(audit={"ticket": "CTX-42"}),
    },
    "ON_DENY": {
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
        "extra_tags": _evaluate_id_entries("ON_DENY")[0] + _kv(**{"ai_guard.policy_name": "destructive-actions"}),
        "extra_metastruct": _evaluate_id_entries("ON_DENY")[1]
        + _kv(policy_details={"rule": "no-recursive-delete", "severity": "high"}),
    },
    # extra_tags in the map shape of the first draft of the contract: ignored as a whole, while the
    # well-formed extra_metastruct next to it is still applied.
    "EXTRA_TAGS_NOT_A_LIST": {
        "messages": [{"role": "user", "content": "What time does the print edition close tonight?"}],
        "action": "ALLOW",
        "tags": [],
        "extra_tags": {"ai_guard.policy_name": "newsroom-default"},
        "extra_metastruct": _kv(policy={"name": "newsroom-default"}),
        "expected_tags": {},
        "expected_metastruct": {"policy": {"name": "newsroom-default"}},
        "skipped_tags": ["ai_guard.policy_name"],
    },
    "EXTRA_METASTRUCT_NOT_A_LIST": {
        "messages": [{"role": "user", "content": "Who is on call for the overnight desk?"}],
        "action": "ALLOW",
        "tags": [],
        "extra_tags": _kv(**{"ai_guard.policy_name": "newsroom-default"}),
        "extra_metastruct": {"policy": {"name": "newsroom-default"}},
        "expected_tags": {"ai_guard.policy_name": "newsroom-default"},
        "expected_metastruct": {},
        "skipped_tags": [],
    },
    # Each malformed entry is skipped on its own: the well-formed entries around it still land.
    # extra_tags only carries strings, so a number or an object there is skipped too, and never
    # rerouted to the meta struct.
    "MALFORMED_ENTRIES": {
        "messages": [{"role": "user", "content": "When does the weekend magazine go to print?"}],
        "action": "ALLOW",
        "tags": [],
        "extra_tags": [
            "ai_guard.policy_name=newsroom-default",
            ["ai_guard.policy_name", "newsroom-default"],
            {"value": "missing key"},
            {"key": 1, "value": "integer key"},
            {"key": "", "value": "empty key"},
            {"key": "ai_guard.policy_revision", "value": 7},
            {"key": "ai_guard.policy_details", "value": {"rule": "embargo-check"}},
            {"key": "ai_guard.policy_name", "value": "newsroom-default"},
        ],
        "extra_metastruct": [
            "policy=newsroom-default",
            {"value": {"name": "missing key"}},
            {"key": 1, "value": {"name": "integer key"}},
            {"key": "", "value": {"name": "empty key"}},
            {"key": "policy", "value": {"name": "newsroom-default"}},
        ],
        "expected_tags": {"ai_guard.policy_name": "newsroom-default"},
        "expected_metastruct": {"policy": {"name": "newsroom-default"}},
        "skipped_tags": ["ai_guard.policy_revision", "ai_guard.policy_details"],
    },
}


def _as_mapping(name: str, field: str, entries: list[dict] | None) -> dict:
    """The {key: value} a well-formed list of {key, value} objects must produce on the span."""
    if entries is None:
        return {}
    keys = [entry["key"] for entry in entries]
    assert len(keys) == len(set(keys)), f"{name}: the backend never repeats a key in {field}"
    return {entry["key"]: entry["value"] for entry in entries}


def _with_expectations(name: str, scenario: dict) -> dict:
    """Return the scenario with its evaluation ID and the tags and meta struct values the tracer must apply."""
    scenario = {"evaluation_id": _evaluation_id(name), **scenario}
    if "expected_tags" not in scenario:
        scenario["expected_tags"] = _as_mapping(name, "extra_tags", scenario.get("extra_tags"))
        scenario["expected_metastruct"] = _as_mapping(name, "extra_metastruct", scenario.get("extra_metastruct"))
        scenario["skipped_tags"] = []
    assert all(isinstance(value, str) for value in scenario["expected_tags"].values()), (
        f"{name}: extra_tags only carries strings"
    )
    return scenario


def _response_body(name: str, scenario: dict) -> str:
    attributes = {
        "action": scenario["action"],
        "is_blocking_enabled": True,
        "reason": DENY_REASON if scenario["action"] == "DENY" else NO_MATCH_REASON,
        "sds_findings": [],
        "tag_probs": _tag_probs_for(scenario["tags"]),
        "tags": scenario["tags"],
    }
    # Both attributes are omitted, not null, when the backend has nothing to send.
    for field in ("extra_tags", "extra_metastruct"):
        if field in scenario:
            attributes[field] = scenario[field]
    return json.dumps({"data": {"id": _evaluation_id(name), "type": "evaluations", "attributes": attributes}})


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
        contents[cassette] = render_cassette(request_body, _response_body(name, scenario))
        owners[cassette] = name
        sidecar[name] = {**_with_expectations(name, scenario), "cassette": cassette}

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
        print(f"{name:30s} -> {entry['cassette']}")
    print(f"\nwrote {len(sidecar)} scenarios -> {SIDECAR}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
