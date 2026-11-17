"""Step 6: check, without a model, that every candidate quotes real data.

Usage:
    python3 -m utils.scripts.review_learning.verify_quotes --run .review-learning/run

Reads candidates/*.json from the extract step. Writes verified.json and unverified.json.
A quote must be a literal part of the cited comment, after whitespace and case are normalized.
Quoted lines (starting with ">") are removed first, so that a reply that quotes a reviewer
cannot be credited as the reviewer's own words. The author and the association come from the
data, never from the model.

Adapted from prlore (src/reconciler/verify-evidence.ts).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import TYPE_CHECKING

from utils.scripts.review_learning.common import read_json, write_json

if TYPE_CHECKING:
    from collections.abc import Iterator

    from utils.scripts.review_learning.common import Json

MIN_QUOTE_CHARS = 10
QUOTED_SIGNALS = {"correction", "disagreement", "human_only", "context"}
FIX_SIGNALS = {"miss", "absence"}
SIGNALS = QUOTED_SIGNALS | FIX_SIGNALS
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    own_lines = [line for line in text.splitlines() if not line.lstrip().startswith(">")]
    return _SPACES.sub(" ", " ".join(own_lines)).strip().lower()


def all_comments(pr: Json) -> Iterator[Json]:
    """Yield every human comment. A thread comment carries the outcome of its thread."""
    yield from pr["comments"]
    yield from pr["reviews"]
    for thread in pr["threads"]:
        yield from ({**comment, "outcome": thread["outcome"]} for comment in thread["comments"])


def comments_by_url(prs: list[Json]) -> dict[str, Json]:
    return {
        c["url"]: {**c, "pr": pr["number"], "pr_author": pr["author"]["login"]}
        for pr in prs
        for c in all_comments(pr)
        if c["url"]
    }


def check_quote(candidate: Json, comments: dict[str, Json]) -> tuple[str | None, Json]:
    """Return the reason for a failure, or None, and the candidate with the author taken from the data."""
    comment = comments.get(candidate.get("comment_url") or "")
    if comment is None or comment["pr"] != candidate["pr"]:
        return "comment_url is not a human comment of this pull request", candidate
    quote = normalize(candidate.get("quote") or "")
    if len(quote) < MIN_QUOTE_CHARS or quote not in normalize(comment["body"]):
        return "quote is not a literal part of the comment", candidate
    author = comment["author"]
    if candidate["signal"] == "correction" and author["login"] == comment["pr_author"]:
        return "a correction must come from a reviewer, not from the author of the pull request", candidate
    rebound = {"author": author["login"], "association": author["association"], "outcome": comment.get("outcome")}
    return None, {**candidate, **rebound}


def check_fix(candidate: Json, fixes: dict[int, Json]) -> str | None:
    fix = fixes.get(candidate["pr"])
    if fix is None or "culprits" not in fix:
        return "the pull request is not a fix with a culprit"
    if candidate.get("culprit_pr") not in {culprit["pr"] for culprit in fix["culprits"]}:
        return "culprit_pr is not a culprit of this fix"
    if candidate["signal"] == "absence" and not fix["absence"]:
        return "szz.py did not mark this fix as an absence"
    return None


def verify(candidate: Json, comments: dict[str, Json], fixes: dict[int, Json]) -> tuple[str | None, Json]:
    if not isinstance(candidate.get("pr"), int) or isinstance(candidate.get("pr"), bool):
        return "pr must be the number of the pull request", candidate
    if candidate.get("signal") not in SIGNALS:
        return f"unknown signal {candidate.get('signal')}", candidate
    if candidate["signal"] in FIX_SIGNALS:
        return check_fix(candidate, fixes), candidate
    return check_quote(candidate, comments)


def load_candidates(run_dir: Path) -> list[Json]:
    """Read only the candidates of the batches in the manifest, so that files from an older run never count."""
    batches = read_json(run_dir / "batches" / "manifest.json")["batches"]
    paths = [run_dir / "candidates" / f"{Path(batch['file']).stem}.json" for batch in batches]
    return [c for path in paths if path.is_file() for c in read_json(path)["candidates"]]


def verify_run(run_dir: Path) -> tuple[list[Json], list[Json]]:
    comments = comments_by_url(read_json(run_dir / "filtered.json"))
    fixes = {fix["fix_pr"]: fix for fix in read_json(run_dir / "fixes.json")}
    verified: list[Json] = []
    unverified: list[Json] = []
    for candidate in load_candidates(run_dir):
        reason, checked = verify(candidate, comments, fixes)
        if reason:
            unverified.append({**candidate, "reason": reason})
        else:
            verified.append(checked)
    write_json(run_dir / "verified.json", verified)
    write_json(run_dir / "unverified.json", unverified)
    return verified, unverified


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    verified, unverified = verify_run(args.run)
    print(f"{len(verified)} candidates verified, {len(unverified)} rejected -> {args.run}")


if __name__ == "__main__":
    main()
