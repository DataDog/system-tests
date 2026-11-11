"""Decide, without a model, what happened to a review thread that a human opened.

Adapted from sphinx (jb-claude-marketplace, skills/sphinx/scripts/sphinx-extract.py,
_classify_thread_outcome). Sphinx classifies threads that it opened itself; this version
classifies threads that a human reviewer opened, and also uses the commits of the pull request.

Usage:
    python3 -m utils.scripts.review_learning.thread_outcome --run .review-learning/run --pr 8399
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from utils.scripts.review_learning.common import read_json

if TYPE_CHECKING:
    from utils.scripts.review_learning.common import Json

APPLIED = "applied"  # the author changed the code after the comment
DISPUTED = "disputed"  # a human pushed back with a reason
DISCUSSED = "discussed"  # humans replied, without a clear result
RESOLVED = "resolved"  # resolved, but no later commit shows a change
IGNORED = "ignored"  # nobody replied and nothing changed

DISMISSIVE = re.compile(
    r"\b(won'?t fix|not going to (fix|change|do)|disagree|false positive|not a bug|intended|on purpose|by design)\b",
    re.IGNORECASE,
)
CONFIRMATIONS = ("fixed in", "addressed in", "resolved in", "applied in", "done in", "changed in", "updated in")
SHORT_CONFIRMATIONS = {"done", "fixed", "addressed", "updated", "changed", "good catch", "good point"}
_SHA = re.compile(r"\b[0-9a-f]{7,40}\b")
_PUNCTUATION = re.compile(r"[^\w\s']")


def is_dismissive(body: str) -> bool:
    return bool(DISMISSIVE.search(body))


def is_confirmation(body: str) -> bool:
    lowered = body.lower()
    if any(keyword in lowered for keyword in CONFIRMATIONS):
        return True
    words = _PUNCTUATION.sub("", lowered).strip()
    if words in SHORT_CONFIRMATIONS:
        return True
    return bool(_SHA.search(lowered)) and any(word in lowered for word in ("fixed", "done", "addressed"))


def has_later_commit(commits: list[Json], created_at: str) -> bool:
    """ISO 8601 timestamps in UTC compare correctly as strings."""
    return any(commit["date"] > created_at for commit in commits)


def classify(thread: Json, commits: list[Json]) -> str:
    """Return the outcome of a thread. The first comment opens it; the others are human replies."""
    opener, replies = thread["comments"][0], thread["comments"][1:]
    if any(is_dismissive(reply["body"]) for reply in replies):
        return DISPUTED
    changed = thread["is_outdated"] and has_later_commit(commits, opener["created_at"])
    if changed or any(is_confirmation(reply["body"]) for reply in replies):
        return APPLIED
    if replies:
        return DISCUSSED
    if thread["is_resolved"] or opener["thumbs_up"] > opener["thumbs_down"]:
        return RESOLVED
    return IGNORED


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--pr", type=int, required=True)
    args = parser.parse_args()
    pr = read_json(args.run / "evidence" / f"{args.pr}.json")
    outcomes = [
        {
            "path": thread["path"],
            "opened_by": thread["comments"][0]["author"]["login"],
            "outcome": classify(thread, pr["commits"]),
        }
        for thread in pr["threads"]
        if thread["comments"]
    ]
    print(json.dumps(outcomes, indent=2))


if __name__ == "__main__":
    main()
