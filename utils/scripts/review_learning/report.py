"""Render report.md from the decisions of decide.py. Used by decide.py; it has no command of its own."""

from __future__ import annotations

from typing import TYPE_CHECKING

from utils.scripts.review_learning.common import REPOSITORY, read_json

if TYPE_CHECKING:
    from pathlib import Path

    from utils.scripts.review_learning.common import Json

SECTIONS = [
    ("apply", "Proposed rule changes"),
    ("needs_decision", "Needs a human decision"),
    ("report_only", "Defects that a rule already describes"),
]
NOT_APPLIED = ("not_enough_evidence", "invalid", "rejected_before", "over_cap")


def pr_link(number: int) -> str:
    return f"[#{number}](https://github.com/{REPOSITORY}/pull/{number})"


def _count(path: Path) -> int:
    return len(read_json(path)) if path.is_file() else 0


def summary_rows(run_dir: Path, decisions: list[Json]) -> list[tuple[str, int]]:
    statuses = [d["status"] for d in decisions]
    return [
        ("Merged pull requests", len(read_json(run_dir / "index.json")["pull_requests"])),
        ("Excluded as automated", _count(run_dir / "excluded.json")),
        ("Fixes with a culprit", _count(run_dir / "fixes.json")),
        ("Verified candidates", _count(run_dir / "verified.json")),
        ("Candidates with a quote that does not match", _count(run_dir / "unverified.json")),
        ("Proposals", len(decisions)),
        ("Ready to apply", statuses.count("apply")),
    ]


def summary(run_dir: Path, decisions: list[Json]) -> list[str]:
    index = read_json(run_dir / "index.json")
    rows = [f"| {label} | {value} |" for label, value in summary_rows(run_dir, decisions)]
    return [f"# Review learning: {index['start']} to {index['end']}", "", "| | Count |", "| --- | ---: |", *rows]


def evidence_lines(decision: Json) -> list[str]:
    lines = []
    for candidate in decision["evidence"]:
        quote = f': "{candidate["quote"]}"' if candidate.get("quote") else ""
        culprit = f" (culprit {pr_link(candidate['culprit_pr'])})" if candidate.get("culprit_pr") else ""
        lines.append(f"  - {pr_link(candidate['pr'])} `{candidate['signal']}`{culprit}{quote}")
    return lines


def change_block(decision: Json) -> list[str]:
    title = f"### {decision.get('rule_id') or 'new rule'} · `{decision['action']}` · {decision['lens']}"
    lines = [title, "", decision.get("status_reason") or decision.get("reason", ""), ""]
    if decision.get("current_text"):
        lines += ["Current:", "", f"> {decision['current_text']}", ""]
    if decision.get("proposed_text"):
        lines += ["Proposed:", "", f"> {decision['proposed_text']}", ""]
    if decision.get("severity"):
        lines += [f"Proposed severity: {decision['severity']}. {decision.get('severity_reason', '')}", ""]
    return [*lines, "Evidence:", *evidence_lines(decision), ""]


def not_applied(decisions: list[Json]) -> list[str]:
    rows = [d for d in decisions if d["status"] in NOT_APPLIED]
    if not rows:
        return []
    lines = ["## Not applied", "", "| Rule | Action | Status | Reason |", "| --- | --- | --- | --- |"]
    lines += [f"| {d.get('rule_id') or '-'} | {d['action']} | {d['status']} | {d['status_reason']} |" for d in rows]
    return [*lines, ""]


def human_only(run_dir: Path) -> list[str]:
    verified = read_json(run_dir / "verified.json")
    items = [c for c in verified if c["signal"] in {"human_only", "context"}]
    if not items:
        return []
    lines = ["## Human-only review and outside context", "", "These are never rule material. A person decides."]
    return [*lines, "", *[f"- {pr_link(c['pr'])} `{c['signal']}`: {c.get('defect', '')}" for c in items], ""]


def coverage(decisions: list[Json], lenses: list[str]) -> list[str]:
    answered = {d["lens"] for d in decisions}
    return ["## Coverage", "", *[f"- {lens}: {'proposals' if lens in answered else 'no proposals'}" for lens in lenses]]


def render(run_dir: Path, decisions: list[Json], lenses: list[str]) -> str:
    lines = [*summary(run_dir, decisions), ""]
    for status, heading in SECTIONS:
        blocks = [block for d in decisions if d["status"] == status for block in change_block(d)]
        lines += [f"## {heading}", "", *(blocks or ["None.", ""])]
    lines += [*not_applied(decisions), *human_only(run_dir), *coverage(decisions, lenses)]
    return "\n".join(lines) + "\n"
