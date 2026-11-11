"""Step 5b: lint every proposed rule text with se (https://github.com/TonyCTHsu/simple-english).

Usage:
    python3 -m utils.scripts.review_learning.plain_english --run .review-learning/run

Reads proposals/*.json and writes lint.json: for each proposal key, the se findings of its
proposed_text. An empty list means that the text passed. The skill sends the findings back to
the model, which fixes the text. decide.py does not apply a text that still has findings.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from utils.scripts.review_learning.common import read_json, write_json

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


def proposal_key(lens: str, index: int) -> str:
    return f"{lens}#{index}"


def iter_proposals(run_dir: Path) -> list[tuple[str, Json]]:
    pairs = []
    for path in sorted((run_dir / "proposals").glob("*.json")):
        data = read_json(path)
        pairs += [(proposal_key(data["lens"], i), p) for i, p in enumerate(data["proposals"])]
    return pairs


def lint_run(run_dir: Path, linter: Linter = se_lint) -> Json:
    findings = {key: linter(p["proposed_text"]) for key, p in iter_proposals(run_dir) if p.get("proposed_text")}
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
