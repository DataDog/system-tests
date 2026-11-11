"""Step 6: decide, without a model, which proposals are strong enough, and write the report.

Usage:
    python3 -m utils.scripts.review_learning.decide --run .review-learning/run

Reads verified.json, proposals/*.json, lint.json, rejected.yml, and the lens files. Writes
decisions.json and report.md. This step never edits a rule file.

The thresholds live here, not in a prompt, so the model cannot talk itself past them.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from utils.scripts.review_learning import report
from utils.scripts.review_learning.common import load_filters, read_json, write_json

if TYPE_CHECKING:
    from collections.abc import Callable

    from utils.scripts.review_learning.common import Json

LENSES_DIR = Path(".agents/rules/code-review")
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
LINT_CHECKS = {"format.sh", "ruff", "mypy", "lint-imports", "yamllint", "yamlfmt", "shellcheck", "manifest parser"}
SEVERITIES = {"P0", "P1"}
MIN_PRS = 2  # distinct pull requests that make a pattern, not a one-off
_RULE_ID = re.compile(r"^### ([A-Z]+-\d+):", re.MULTILINE)

APPLY = "apply"
NEEDS_DECISION = "needs_decision"
NOT_ENOUGH = "not_enough_evidence"
INVALID = "invalid"
REPORT_ONLY = "report_only"
REJECTED_BEFORE = "rejected_before"
OVER_CAP = "over_cap"


def rule_ids(lenses_dir: Path) -> dict[str, set[str]]:
    return {
        lens: set(_RULE_ID.findall((lenses_dir / f"{lens}.md").read_text(encoding="utf-8"))) for lens in LENS_PREFIX
    }


def validate(lens: str, proposal: Json, ids: dict[str, set[str]], lens_text: str) -> str | None:
    """Return why the proposal cannot be applied to the lens file, or None."""
    action, rule_id = proposal.get("action"), proposal.get("rule_id") or ""
    if action not in CHANGE_ACTIONS | REPORT_ACTIONS:
        return f"unknown action {action}"
    if action in EDIT_ACTIONS and rule_id not in ids[lens]:
        return f"{rule_id} is not a rule of {lens}"
    if action in EDIT_ACTIONS and proposal.get("current_text") and proposal["current_text"] not in lens_text:
        return "current_text is not in the lens file"
    if action == "new_rule":
        return validate_new_rule(lens, proposal, ids)
    return None


def validate_new_rule(lens: str, proposal: Json, ids: dict[str, set[str]]) -> str | None:
    rule_id = proposal.get("rule_id") or ""
    if not rule_id.startswith(f"{LENS_PREFIX[lens]}-"):
        return f"a new rule of {lens} must start with {LENS_PREFIX[lens]}-"
    if any(rule_id in lens_ids for lens_ids in ids.values()):
        return f"{rule_id} already exists"
    if proposal.get("severity") not in SEVERITIES:
        return "a new rule needs severity P0 or P1"
    return None


def evidence_gap(proposal: Json, candidates: list[Json], root: Path) -> str | None:
    """Return why the evidence is too weak for this action, or None."""
    rule_signals = [c for c in candidates if c["signal"] not in {"human_only", "context"}]
    if not rule_signals:
        return "no verified evidence that can support a rule change"
    check = EVIDENCE_CHECKS.get(proposal["action"])
    return check(proposal, rule_signals, root) if check else None


def _change_gap(_proposal: Json, candidates: list[Json], _root: Path) -> str | None:
    strong = any(c["signal"] in FIX_SIGNALS or is_maintainer_correction(c) for c in candidates)
    if strong or len({c["pr"] for c in candidates}) >= MIN_PRS:
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


def was_rejected(proposal: Json, prs: set[int], rejected: list[Json]) -> bool:
    """A proposal stays rejected until it brings evidence from a pull request that the rejection did not see."""
    return any(
        r["rule_id"] == proposal.get("rule_id") and r["action"] == proposal["action"] and prs <= set(r["prs"])
        for r in rejected
    )


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
    if was_rejected(proposal, {c["pr"] for c in candidates}, context["rejected"]):
        return REJECTED_BEFORE, "rejected in an earlier pull request, with no new evidence"
    if context["lint"]:
        return NEEDS_DECISION, "se still reports: " + ", ".join(sorted({f["rule"] for f in context["lint"]}))
    return APPLY, proposal.get("reason", "")


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


def decide_proposal(lens: str, index: int, proposal: Json, inputs: Json) -> Json:
    evidence = [inputs["verified"][i] for i in proposal.get("candidate_ids", []) if i in inputs["verified"]]
    context = {**inputs, "evidence": evidence, "lint": inputs["lint"].get(f"{lens}#{index}", [])}
    status, reason = status_of(lens, proposal, context)
    return {"lens": lens, **proposal, "evidence": evidence, "status": status, "status_reason": reason}


def decide_run(run_dir: Path, root: Path, max_changes: int) -> list[Json]:
    inputs = load_inputs(run_dir, root)
    decisions = []
    for path in sorted((run_dir / "proposals").glob("*.json")):
        data = read_json(path)
        decisions += [decide_proposal(data["lens"], i, p, inputs) for i, p in enumerate(data["proposals"])]
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
