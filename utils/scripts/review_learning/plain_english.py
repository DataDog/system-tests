"""Step 8: lint every proposed rule text with se (https://github.com/TonyCTHsu/simple-english).

Usage:
    python3 -m utils.scripts.review_learning.plain_english --run .review-learning/run

Reads proposals/*.json and writes lint.json: for each lens and proposed_text, the se findings.
It lints each text as apply.py writes it in the lens file, with its field prefix, such as "- Detect: ".
se can find a long sentence in that line, and not in the bare text.
An empty list means that the text passed. The skill sends the findings back to the model,
which fixes the text. decide.py does not apply a text that still has findings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from utils.scripts.review_learning.common import FIELD_PREFIX, read_json, write_json

if TYPE_CHECKING:
    from collections.abc import Callable

    from utils.scripts.review_learning.common import Json

    Linter = Callable[[str], list[Json]]

SE_EXIT_FINDINGS = 1


def se_lint(text: str) -> list[Json]:
    """Lint Markdown text with se. Exit code 1 means findings, 2 means an error."""
    result = subprocess.run(["se", "--format", "json", "-"], input=text, capture_output=True, text=True, check=False)
    if result.returncode not in (0, SE_EXIT_FINDINGS):
        raise RuntimeError(f"se failed: {result.stderr.strip()}")
    return [{"rule": f["rule"], "message": f["message"]} for f in json.loads(result.stdout or "[]")]


def proposal_key(lens: str, text: str) -> str:
    """Key a finding by its lens and text, so that a rewrite or a new order of the proposals cannot mix them up."""
    return f"{lens}#{hashlib.sha256(text.encode()).hexdigest()[:16]}"


def as_written(proposal: Json) -> str:
    """The line that apply.py writes for an edit of one field. A new rule is already a whole block."""
    text, prefix = proposal["proposed_text"], FIELD_PREFIX.get(proposal.get("field") or "")
    if proposal.get("action") == "new_rule":
        return text.strip()  # apply.py strips a new block too
    return prefix + text if prefix else text


def iter_texts(run_dir: Path) -> list[tuple[str, str, str]]:
    """Return the lens, the proposed text, and the text as it appears in the lens file."""
    triples = []
    for path in sorted((run_dir / "proposals").glob("*.json")):
        data = read_json(path)
        proposals = [p for p in data["proposals"] if p.get("proposed_text")]
        triples += [(data["lens"], p["proposed_text"], as_written(p)) for p in proposals]
    return triples


def lint_run(run_dir: Path, linter: Linter = se_lint) -> Json:
    findings: Json = {}
    for lens, text, written in iter_texts(run_dir):
        # Two proposals can share a text in different fields. Keep the findings of both: one never hides the other.
        findings.setdefault(proposal_key(lens, text), []).extend(linter(written))
    write_json(run_dir / "lint.json", findings)
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    findings = lint_run(args.run)
    failing = sorted(key for key, items in findings.items() if items)
    print(f"{len(findings)} texts linted, {len(failing)} with findings: {', '.join(failing) or 'none'}")


if __name__ == "__main__":
    main()
