"""Step 7: apply the decisions with the status apply to the lens files.

Usage:
    python3 -m utils.scripts.review_learning.apply --run .review-learning/run

Reads decisions.json, and edits .agents/rules/code-review/<lens>.md in the working tree.
Writes applied.json with the result of each decision. Review the change with git diff, and
undo it with git checkout.

Each rule is a block that starts with "### <ID>:", and each field is one line, such as
"- Detect: ..." or "- ✅ ...". An edit replaces the value of one field line. It never
rewrites the rest of the rule.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import TYPE_CHECKING

from utils.scripts.review_learning.common import FIELD_PREFIX, read_json, run, write_json
from utils.scripts.review_learning.decide import LENSES_DIR

if TYPE_CHECKING:
    from utils.scripts.review_learning.common import Json

INSERT_AFTER = ("Not when", "Detect", "Flag")  # a missing field goes after the first of these
_HEADING = re.compile(r"^### ([A-Z]+-\d+):")


class ApplyError(ValueError):
    """The decision does not match the lens file, so it is not applied."""


def rule_block(lines: list[str], rule_id: str) -> tuple[int, int]:
    """Return the first and the end line index of a rule block."""
    starts = [i for i, line in enumerate(lines) if line.startswith(f"### {rule_id}:")]
    if len(starts) != 1:
        raise ApplyError(f"{rule_id} appears {len(starts)} times in the lens file")
    end = next((i for i in range(starts[0] + 1, len(lines)) if lines[i].startswith("### ")), len(lines))
    return starts[0], end


def set_field(block: list[str], field: str, current: str | None, value: str) -> list[str]:
    """Replace the line that holds the current text, or add the field when the rule has none."""
    prefix = FIELD_PREFIX.get(field)
    if prefix is None:
        raise ApplyError(f"unknown field {field}")
    return replace_line(block, prefix, current, value) if current is not None else add_line(block, prefix, value)


def replace_line(block: list[str], prefix: str, current: str, value: str) -> list[str]:
    matches = [i for i, line in enumerate(block) if line == prefix + current]
    if len(matches) != 1:
        raise ApplyError(f"the line '{prefix}' with current_text appears {len(matches)} times in the rule")
    return [*block[: matches[0]], prefix + value, *block[matches[0] + 1 :]]


def add_line(block: list[str], prefix: str, value: str) -> list[str]:
    if any(line.startswith(prefix) for line in block):
        raise ApplyError(f"the rule already has a '{prefix.strip()}' line, so current_text is required")
    anchors = [i for name in INSERT_AFTER for i, line in enumerate(block) if line.startswith(FIELD_PREFIX[name])]
    at = anchors[0] + 1 if anchors else len(block)
    return [*block[:at], prefix + value, *block[at:]]


def edit_rule(text: str, decision: Json) -> str:
    lines = text.splitlines()
    start, end = rule_block(lines, decision["rule_id"])
    block = set_field(lines[start:end], decision["field"], decision.get("current_text"), decision["proposed_text"])
    return "\n".join([*lines[:start], *block, *lines[end:]]) + "\n"


def add_rule(text: str, decision: Json) -> str:
    block = decision["proposed_text"].strip()
    if not block.startswith(f"### {decision['rule_id']}: "):
        raise ApplyError(f"a new rule must start with '### {decision['rule_id']}: '")
    if f"- Severity: {decision['severity']}" not in block or "\n- Flag: " not in block:
        raise ApplyError("a new rule needs its Severity line and a Flag line")
    return text.rstrip() + "\n\n" + block + "\n"


def check_lens(text: str) -> None:
    """Every rule keeps a unique ID, a Severity line, and a Flag line."""
    ids = [m.group(1) for line in text.splitlines() if (m := _HEADING.match(line))]
    if len(ids) != len(set(ids)):
        raise ApplyError("two rules share an ID")
    lines = text.splitlines()
    for rule_id in ids:
        start, end = rule_block(lines, rule_id)
        block = lines[start:end]
        if not any(line.startswith("- Severity: ") for line in block) or not any(
            line.startswith("- Flag: ") for line in block
        ):
            raise ApplyError(f"{rule_id} lost its Severity or Flag line")


def apply_one(text: str, decision: Json) -> str:
    changed = add_rule(text, decision) if decision["action"] == "new_rule" else edit_rule(text, decision)
    check_lens(changed)
    return changed


def is_clean(path: Path, root: Path) -> bool:
    """Only edit a lens file without local changes, so that git checkout undoes exactly this step."""
    return not run(["git", "status", "--porcelain", "--", str(path.relative_to(root))], cwd=root).strip()


def apply_lens(path: Path, decisions: list[Json], root: Path) -> list[Json]:
    if not is_clean(path, root):
        return [{**_summary(d), "result": "skipped", "reason": "the lens file has local changes"} for d in decisions]
    text, results = path.read_text(encoding="utf-8"), []
    for decision in decisions:
        try:
            text = apply_one(text, decision)
            results.append({**_summary(decision), "result": "applied"})
        except ApplyError as error:
            results.append({**_summary(decision), "result": "skipped", "reason": str(error)})
    if text != path.read_text(encoding="utf-8"):
        path.write_text(text, encoding="utf-8")
    return results


def _summary(decision: Json) -> Json:
    return {key: decision.get(key) for key in ("lens", "rule_id", "action", "field")}


def apply_run(run_dir: Path, root: Path) -> list[Json]:
    ready = [d for d in read_json(run_dir / "decisions.json") if d["status"] == "apply"]
    results = []
    for lens in sorted({d["lens"] for d in ready}):
        path = root / LENSES_DIR / f"{lens}.md"
        results += apply_lens(path, [d for d in ready if d["lens"] == lens], root)
    write_json(run_dir / "applied.json", results)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    results = apply_run(args.run, args.repo_root.resolve())
    applied = sum(r["result"] == "applied" for r in results)
    print(f"{applied} of {len(results)} changes applied. Review them with: git diff {LENSES_DIR}")
    for result in results:
        if result["result"] != "applied":
            print(f"  skipped {result['rule_id']} {result['action']}: {result['reason']}")


if __name__ == "__main__":
    main()
