"""Step 9: decide, without a model, which proposals are strong enough, and write the report.

Usage:
    python3 -m utils.scripts.review_learning.decide --run .review-learning/run

Reads verified.json, proposals/*.json, lint.json, rejected.yml, and the lens files. Writes
decisions.json and report.md. This step never edits a rule file.

The thresholds live here, not in a prompt, so the model cannot talk itself past them. Sources:
- Two pull requests, or one maintainer correction: the recurrence floor of prlore
  (src/reconciler/score.ts).
- One clear fix is enough, and a cap on changes for each run: tessl, tune-review-lenses and
  learn-from-review-feedback.
- A real fix ranks first under the cap: tacit (synthesizer, "What actually broke").
- An exception only adds text, and contradictions go to a person: sphinx, learn step 7.6
  (jb-claude-marketplace, skills/sphinx/subskills/learn/SKILL.md).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from utils.scripts.review_learning import report
from utils.scripts.review_learning import apply as apply_step
from utils.scripts.review_learning.common import (
    FIELD_PREFIX,
    LENSES_DIR,
    RULE_HEADING,
    load_filters,
    read_json,
    write_json,
)
from utils.scripts.review_learning.plain_english import proposal_key

if TYPE_CHECKING:
    from collections.abc import Callable

    from utils.scripts.review_learning.common import Json

LENS_PREFIX = {
    "test-effectiveness": "TEST",
    "lifecycle-and-isolation": "LIFE",
    "activation-and-metadata": "META",
    "infrastructure-and-conventions": "INFRA",
}
EDIT_ACTIONS = {"sharpen", "add_not_when", "lint_owned"}
CHANGE_ACTIONS = EDIT_ACTIONS | {"new_rule"}
REPORT_ACTIONS = {"covered", "contested", "out_of_lens"}
MAINTAINERS = {"OWNER", "MEMBER", "COLLABORATOR"}
FIX_SIGNALS = {"miss", "absence"}
CHANGE_SIGNALS = FIX_SIGNALS | {"correction"}  # evidence that a pattern is a defect
LINT_CHECKS = {"format.sh", "ruff", "mypy", "lint-imports", "yamllint", "yamlfmt", "shellcheck", "manifest parser"}
SEVERITIES = {"P0", "P1"}
MIN_PRS = 2  # distinct pull requests that make a pattern, not a one-off

APPLY = "apply"
NEEDS_DECISION = "needs_decision"
NOT_ENOUGH = "not_enough_evidence"
INVALID = "invalid"
REPORT_ONLY = "report_only"
REJECTED_BEFORE = "rejected_before"
OVER_CAP = "over_cap"


def rule_ids(lenses_dir: Path) -> dict[str, set[str]]:
    return {
        lens: set(RULE_HEADING.findall((lenses_dir / f"{lens}.md").read_text(encoding="utf-8"))) for lens in LENS_PREFIX
    }


def validate(lens: str, proposal: Json, ids: dict[str, set[str]], lens_text: str) -> str | None:
    """Return why the proposal cannot be applied to the lens file, or None."""
    action = proposal.get("action")
    if action not in CHANGE_ACTIONS | REPORT_ACTIONS:
        return f"unknown action {action}"
    if action in CHANGE_ACTIONS and not proposal.get("proposed_text"):
        return "a change needs a proposed_text"
    if action in EDIT_ACTIONS:
        return validate_edit(lens, proposal, ids, lens_text)
    if action == "new_rule":
        return validate_new_rule(lens, proposal, ids, lens_text)
    return None


def validate_edit(lens: str, proposal: Json, ids: dict[str, set[str]], lens_text: str) -> str | None:
    """An edit names a rule and a field. Only add_not_when can add a field, so it alone can omit current_text."""
    current = proposal.get("current_text")
    if proposal.get("rule_id") not in ids[lens]:
        return f"{proposal.get('rule_id')} is not a rule of {lens}"
    if proposal.get("field") not in FIELD_PREFIX:
        return f"field must be one of {', '.join(FIELD_PREFIX)}"
    if not current and proposal["action"] != "add_not_when":
        return "an edit needs the current_text that it replaces"
    return dry_run(proposal, lens_text)


def dry_run(proposal: Json, lens_text: str) -> str | None:
    """Run the edit on a copy of the lens. apply.py is the only judge of what it can apply."""
    try:
        apply_step.apply_one(lens_text, proposal)
    except apply_step.ApplyError as error:
        return str(error)
    return None


def validate_new_rule(lens: str, proposal: Json, ids: dict[str, set[str]], lens_text: str) -> str | None:
    rule_id = proposal.get("rule_id") or ""
    if not rule_id.startswith(f"{LENS_PREFIX[lens]}-"):
        return f"a new rule of {lens} must start with {LENS_PREFIX[lens]}-"
    if any(rule_id in lens_ids for lens_ids in ids.values()):
        return f"{rule_id} already exists"
    if proposal.get("severity") not in SEVERITIES:
        return "a new rule needs severity P0 or P1"
    return dry_run(proposal, lens_text)


def evidence_gap(proposal: Json, candidates: list[Json], root: Path) -> str | None:
    """Return why the evidence is too weak for this action, or None."""
    rule_signals = [c for c in candidates if c["signal"] not in {"human_only", "context"}]
    if not rule_signals:
        return "no verified evidence that can support a rule change"
    check = EVIDENCE_CHECKS.get(proposal["action"])
    return check(proposal, rule_signals, root) if check else None


def _change_gap(_proposal: Json, candidates: list[Json], _root: Path) -> str | None:
    """A disagreement defends a pattern, so it never counts toward a stricter rule."""
    defects = [c for c in candidates if c["signal"] in CHANGE_SIGNALS]
    strong = any(c["signal"] in FIX_SIGNALS or is_maintainer_correction(c) for c in defects)
    if strong or len({c["pr"] for c in defects}) >= MIN_PRS:
        return None
    return "needs a fix, an applied maintainer correction, or two PRs"


def _not_when_gap(proposal: Json, candidates: list[Json], root: Path) -> str | None:
    disagreements = {c["pr"] for c in candidates if c["signal"] == "disagreement"}
    if len(disagreements) >= MIN_PRS or (disagreements and cites_written_decision(proposal.get("cited_path"), root)):
        return None
    return "needs two PRs or a written decision"


def _lint_gap(proposal: Json, _candidates: list[Json], _root: Path) -> str | None:
    return None if proposal.get("lint_check") in LINT_CHECKS else "lint_check must name a format.sh check"


EVIDENCE_CHECKS: dict[str, Callable[[Json, list[Json], Path], str | None]] = {
    "new_rule": _change_gap,
    "sharpen": _change_gap,
    "add_not_when": _not_when_gap,
    "lint_owned": _lint_gap,
}


def is_maintainer_correction(candidate: Json) -> bool:
    return (
        candidate["signal"] == "correction"
        and candidate.get("outcome") == "applied"
        and candidate.get("association") in MAINTAINERS
    )


def cites_written_decision(path: str | None, root: Path) -> bool:
    return path is not None and path.startswith(("docs/", ".agents/")) and (root / path).is_file()


def was_rejected(lens: str, proposal: Json, prs: set[int], rejected: list[Json]) -> bool:
    """A proposal stays rejected until it brings evidence from a pull request that the rejection did not see.

    A new rule gets a new ID in each run, so a rejected new rule matches by lens, not by ID.
    """
    return any(
        r["action"] == proposal["action"] and same_target(lens, proposal, r) and prs <= set(r["prs"]) for r in rejected
    )


def same_target(lens: str, proposal: Json, rejection: Json) -> bool:
    if proposal["action"] == "new_rule":
        return rejection.get("lens") == lens
    return rejection.get("rule_id") == proposal.get("rule_id")


def strength(decision: Json) -> tuple[bool, int, bool]:
    candidates = decision["evidence"]
    return (
        any(c["signal"] in FIX_SIGNALS for c in candidates),
        len({c["pr"] for c in candidates}),
        any(is_maintainer_correction(c) for c in candidates),
    )


def status_of(lens: str, proposal: Json, context: Json) -> tuple[str, str]:
    """Return the status and its reason for one proposal, before the cap on changes."""
    if reason := validate(lens, proposal, context["ids"], context["lens_text"][lens]):
        return INVALID, reason
    if proposal["action"] in REPORT_ACTIONS:
        return (NEEDS_DECISION if proposal["action"] == "contested" else REPORT_ONLY), proposal.get("reason", "")
    candidates = context["evidence"]
    if reason := evidence_gap(proposal, candidates, context["root"]):
        return NOT_ENOUGH, reason
    if was_rejected(lens, proposal, {c["pr"] for c in candidates}, context["rejected"]):
        return REJECTED_BEFORE, "rejected in an earlier pull request, with no new evidence"
    if reason := lint_gap(context["lint"]):
        return NEEDS_DECISION, reason
    return APPLY, proposal.get("reason", "")


def lint_gap(findings: list[Json] | None) -> str | None:
    """Fail closed: a text that was not linted needs a person, like a text with findings."""
    if findings is None:
        return "plain_english.py did not lint this text"
    return "se still reports: " + ", ".join(sorted({f["rule"] for f in findings})) if findings else None


def mark_duplicate_new_ids(decisions: list[Json]) -> None:
    """Two new rules in one run cannot share an ID. The first one keeps it."""
    seen: set[str] = set()
    for decision in decisions:
        if decision["action"] != "new_rule" or decision["status"] == INVALID:
            continue
        if decision["rule_id"] in seen:
            decision["status"], decision["status_reason"] = (
                INVALID,
                f"{decision['rule_id']} is already proposed in this run",
            )
        seen.add(decision["rule_id"])


def apply_cap(decisions: list[Json], max_changes: int) -> None:
    ready = sorted((d for d in decisions if d["status"] == APPLY), key=strength, reverse=True)
    for decision in ready[max_changes:]:
        decision["status"], decision["status_reason"] = OVER_CAP, f"more than {max_changes} changes in this run"


def load_inputs(run_dir: Path, root: Path) -> Json:
    rejected_path = root / "utils/scripts/review_learning/rejected.yml"
    lenses_dir = root / LENSES_DIR
    return {
        "verified": {c["id"]: c for c in read_json(run_dir / "verified.json")},
        "lint": read_json(run_dir / "lint.json") if (run_dir / "lint.json").is_file() else {},
        "rejected": yaml.safe_load(rejected_path.read_text(encoding="utf-8")) or [],
        "ids": rule_ids(lenses_dir),
        "lens_text": {lens: (lenses_dir / f"{lens}.md").read_text(encoding="utf-8") for lens in LENS_PREFIX},
        "root": root,
    }


def lint_findings(lens: str, proposal: Json, lint: Json) -> list[Json] | None:
    """Return the se findings of the proposed text, an empty list when it has none, or None when it was not linted."""
    text = proposal.get("proposed_text")
    return lint.get(proposal_key(lens, text)) if text else []


def decide_proposal(lens: str, proposal: Json, inputs: Json) -> Json:
    evidence = [inputs["verified"][i] for i in proposal.get("candidate_ids", []) if i in inputs["verified"]]
    if lens not in LENS_PREFIX:
        return {
            "lens": lens,
            **proposal,
            "evidence": evidence,
            "status": INVALID,
            "status_reason": f"unknown lens {lens}",
        }
    context = {**inputs, "evidence": evidence, "lint": lint_findings(lens, proposal, inputs["lint"])}
    status, reason = status_of(lens, proposal, context)
    return {"lens": lens, **proposal, "evidence": evidence, "status": status, "status_reason": reason}


def decide_run(run_dir: Path, root: Path, max_changes: int) -> list[Json]:
    inputs = load_inputs(run_dir, root)
    decisions = []
    for path in sorted((run_dir / "proposals").glob("*.json")):
        data = read_json(path)
        decisions += [decide_proposal(data["lens"], p, inputs) for p in data["proposals"]]
    mark_duplicate_new_ids(decisions)
    apply_cap(decisions, max_changes)
    write_json(run_dir / "decisions.json", decisions)
    (run_dir / "report.md").write_text(report.render(run_dir, decisions, list(LENS_PREFIX)), encoding="utf-8")
    return decisions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--max-changes", type=int, default=load_filters().defaults["max_changes"])
    args = parser.parse_args()
    decisions = decide_run(args.run, args.repo_root, args.max_changes)
    ready = sum(d["status"] == APPLY for d in decisions)
    print(f"{len(decisions)} proposals, {ready} ready to apply -> {args.run / 'report.md'}")


if __name__ == "__main__":
    main()
