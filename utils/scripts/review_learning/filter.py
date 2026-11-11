"""Step 2: remove automated pull requests and every comment that is not a human review.

Usage:
    python3 -m utils.scripts.review_learning.filter --run .review-learning/run

Reads evidence/*.json and writes:
- filtered.json: the pull requests to mine, with human comments only. Each thread has its outcome.
- excluded.json: the pull requests that were left out, each with the reason.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from utils.scripts.review_learning import thread_outcome
from utils.scripts.review_learning.common import load_filters, matches_any, read_json, write_json

if TYPE_CHECKING:
    from utils.scripts.review_learning.common import Filters, Json

# When a pull request is too long, threads with a weaker outcome are dropped first.
OUTCOME_PRIORITY = [
    thread_outcome.APPLIED,
    thread_outcome.DISPUTED,
    thread_outcome.DISCUSSED,
    thread_outcome.RESOLVED,
    thread_outcome.IGNORED,
]


def exclusion_reason(pr: Json, filters: Filters) -> str | None:
    if pr["number"] in filters.pr_numbers:
        return "listed in exclude_prs.numbers"
    if filters.pr_authors.matches(pr["author"]):
        return f"automated author {pr['author']['login']}"
    if matches_any(pr["title"], filters.pr_title_patterns):
        return "automated title"
    if labels := sorted(set(pr["labels"]) & set(filters.pr_labels)):
        return f"label {labels[0]}"
    return None


def is_human_review(comment: Json, filters: Filters) -> bool:
    if filters.comment_authors.matches(comment["author"]):
        return False
    body = comment["body"].strip()
    return bool(body) and not matches_any(body, filters.comment_body_patterns)


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + " [...]"


def _clean_comment(comment: Json, filters: Filters) -> Json:
    return {**comment, "body": _shorten(comment["body"], filters.defaults["max_chars_per_comment"])}


def clean_thread(thread: Json, commits: list[Json], filters: Filters) -> Json | None:
    """Drop the thread when a bot or an ignored author opened it; otherwise keep its human comments."""
    if not thread["comments"] or not is_human_review(thread["comments"][0], filters):
        return None
    comments = [_clean_comment(c, filters) for c in thread["comments"] if is_human_review(c, filters)]
    cleaned = {**thread, "comments": comments}
    return {**cleaned, "outcome": thread_outcome.classify(cleaned, commits)}


def _size(pr: Json) -> int:
    texts = [pr["body"]] + [c["body"] for c in pr["comments"] + pr["reviews"]]
    texts += [c["body"] for thread in pr["threads"] for c in thread["comments"]]
    return sum(len(text) for text in texts)


def fit_in_budget(pr: Json, max_chars: int) -> Json:
    """Drop the weakest threads until the pull request fits in the budget of the model step."""
    threads = sorted(pr["threads"], key=lambda thread: OUTCOME_PRIORITY.index(thread["outcome"]))
    fitted = {**pr, "threads": threads, "dropped_threads": 0}
    while _size(fitted) > max_chars and fitted["threads"]:
        fitted = {**fitted, "threads": fitted["threads"][:-1], "dropped_threads": fitted["dropped_threads"] + 1}
    return fitted


def clean_pull_request(pr: Json, filters: Filters) -> Json:
    threads = [clean_thread(thread, pr["commits"], filters) for thread in pr["threads"]]
    cleaned = {
        **pr,
        "body": _shorten(pr["body"], filters.defaults["max_chars_per_body"]),
        "comments": [_clean_comment(c, filters) for c in pr["comments"] if is_human_review(c, filters)],
        "reviews": [_clean_comment(r, filters) for r in pr["reviews"] if is_human_review(r, filters)],
        "threads": [thread for thread in threads if thread is not None],
    }
    return fit_in_budget(cleaned, filters.defaults["max_chars_per_pr"])


def filter_run(run_dir: Path, filters: Filters) -> tuple[list[Json], list[Json]]:
    kept: list[Json] = []
    excluded: list[Json] = []
    for path in sorted((run_dir / "evidence").glob("*.json"), key=lambda p: int(p.stem)):
        pr = read_json(path)
        if reason := exclusion_reason(pr, filters):
            excluded.append(
                {"number": pr["number"], "title": pr["title"], "author": pr["author"]["login"], "reason": reason}
            )
        else:
            kept.append(clean_pull_request(pr, filters))
    write_json(run_dir / "filtered.json", kept)
    write_json(run_dir / "excluded.json", excluded)
    return kept, excluded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    kept, excluded = filter_run(args.run, load_filters())
    threads = sum(len(pr["threads"]) for pr in kept)
    print(f"{len(kept)} pull requests kept, {len(excluded)} excluded, {threads} human review threads")


if __name__ == "__main__":
    main()
