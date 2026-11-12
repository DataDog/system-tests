"""Step 1: download the merged pull requests of a time window. This is the only step that uses the network.

Usage:
    python3 -m utils.scripts.review_learning.collect --window 30d
    python3 -m utils.scripts.review_learning.collect --window 2026-10-01..2026-10-31 --out .review-learning/october

Without --out, the run goes to .review-learning/<start>..<end>. Delete old runs with clean.py.

Writes evidence/<number>.json for each pull request and index.json for the run.
Pull request text is data written by third parties. No step ever executes it.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from utils.scripts.review_learning.common import REPOSITORY, RUNS_ROOT, Json, load_filters, run, write_json

if TYPE_CHECKING:
    from collections.abc import Callable

    GraphqlRunner = Callable[[str, dict[str, str]], Json]

SEARCH_LIMIT = 1000  # GitHub search never returns more results than this
PAGE_SIZE = 25

_AUTHOR = "author { login __typename } authorAssociation"
QUERY = f"""
query($q: String!, $after: String) {{
  search(query: $q, type: ISSUE, first: {PAGE_SIZE}, after: $after) {{
    issueCount
    pageInfo {{ hasNextPage endCursor }}
    nodes {{ ... on PullRequest {{
      number title body url mergedAt {_AUTHOR}
      labels(first: 20) {{ totalCount nodes {{ name }} }}
      mergeCommit {{ oid }}
      files(first: 100) {{ totalCount nodes {{ path additions deletions }} }}
      commits(first: 100) {{ totalCount nodes {{ commit {{ oid committedDate messageHeadline }} }} }}
      reviews(first: 50) {{ totalCount nodes {{ {_AUTHOR} state body submittedAt url }} }}
      comments(first: 100) {{ totalCount nodes {{ {_AUTHOR} body createdAt url }} }}
      reviewThreads(first: 100) {{ totalCount nodes {{ isResolved isOutdated path line originalLine
        comments(first: 50) {{ totalCount nodes {{ {_AUTHOR} body createdAt url diffHunk
          reactionGroups {{ content users {{ totalCount }} }} }} }} }} }}
    }} }}
  }}
}}
"""

_RANGE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})$")
_DAYS = re.compile(r"^(\d+)d$")


def parse_window(window: str, today: date) -> tuple[date, date]:
    """Return the first and last merge dates, both included, for '30d' or '2026-10-01..2026-10-31'."""
    if match := _DAYS.match(window):
        days = int(match.group(1))
        if days < 1:
            raise ValueError("a window of days must hold at least 1 day")
        return today - timedelta(days=days - 1), today
    if match := _RANGE.match(window):
        start, end = date.fromisoformat(match.group(1)), date.fromisoformat(match.group(2))
        if start > end:
            raise ValueError(f"window {window} ends before it starts")
        return start, end
    raise ValueError(f"window must look like 30d or 2026-10-01..2026-10-31, not {window}")


def gh_graphql(query: str, variables: dict[str, str]) -> Json:
    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for name, value in variables.items():
        args += ["-f", f"{name}={value}"]
    return json.loads(run(args))


def fetch_pull_requests(repo: str, start: date, end: date, graphql: GraphqlRunner = gh_graphql) -> list[Json]:
    search = f"repo:{repo} is:pr is:merged merged:{start.isoformat()}..{end.isoformat()}"
    variables = {"q": search}
    nodes: list[Json] = []
    while True:
        page = graphql(QUERY, variables)["data"]["search"]
        if page["issueCount"] > SEARCH_LIMIT:
            raise RuntimeError(f"{page['issueCount']} pull requests in the window; use a smaller window")
        nodes += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return nodes
        variables = {"q": search, "after": page["pageInfo"]["endCursor"]}


def _author(node: Json) -> Json:
    author = node.get("author") or {"login": "ghost", "__typename": "User"}
    return {"login": author["login"], "type": author["__typename"], "association": node.get("authorAssociation")}


def _reactions(node: Json) -> tuple[int, int]:
    counts = {group["content"]: group["users"]["totalCount"] for group in node.get("reactionGroups") or []}
    return counts.get("THUMBS_UP", 0), counts.get("THUMBS_DOWN", 0)


def _comment(node: Json) -> Json:
    thumbs_up, thumbs_down = _reactions(node)
    return {
        "author": _author(node),
        "body": node.get("body") or "",
        "created_at": node.get("createdAt") or node.get("submittedAt"),
        "url": node.get("url"),
        "diff_hunk": node.get("diffHunk"),
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
    }


def _thread(node: Json) -> Json:
    return {
        "is_resolved": node["isResolved"],
        "is_outdated": node["isOutdated"],
        "path": node["path"],
        "line": node["line"],
        "original_line": node["originalLine"],
        "comments": [_comment(comment) for comment in node["comments"]["nodes"]],
    }


def _commits(node: Json) -> list[Json]:
    commits = [item["commit"] for item in node["commits"]["nodes"]]
    return [{"oid": c["oid"], "date": c["committedDate"], "headline": c["messageHeadline"]} for c in commits]


CAPPED = ("files", "commits", "reviews", "comments", "reviewThreads")


def truncated(node: Json) -> list[str]:
    """Name the lists that GitHub cut at the query limit, so that the later steps know data is missing."""
    names = [name for name in CAPPED if node[name]["totalCount"] > len(node[name]["nodes"])]
    if any(t["comments"]["totalCount"] > len(t["comments"]["nodes"]) for t in node["reviewThreads"]["nodes"]):
        names.append("thread comments")
    return names


def normalize(node: Json) -> Json:
    """Keep the fields that the later steps use, in a flat shape."""
    return {
        "truncated": truncated(node),
        "number": node["number"],
        "title": node["title"],
        "body": node.get("body") or "",
        "url": node["url"],
        "merged_at": node["mergedAt"],
        "author": _author(node),
        "labels": [label["name"] for label in node["labels"]["nodes"]],
        "merge_commit": (node.get("mergeCommit") or {}).get("oid"),
        "files": node["files"]["nodes"],
        "commits": _commits(node),
        "reviews": [{**_comment(review), "state": review["state"]} for review in node["reviews"]["nodes"]],
        "comments": [_comment(comment) for comment in node["comments"]["nodes"]],
        "threads": [_thread(thread) for thread in node["reviewThreads"]["nodes"]],
    }


def _summary(pr: Json) -> Json:
    return {"number": pr["number"], "title": pr["title"], "author": pr["author"]["login"], "merged_at": pr["merged_at"]}


def clear_evidence(out: Path) -> None:
    for old in (out / "evidence").glob("*.json"):
        old.unlink()


def collect(repo: str, start: date, end: date, out: Path, graphql: GraphqlRunner = gh_graphql) -> Json:
    """Download the window into out. Evidence from an earlier run in the same folder is deleted first."""
    clear_evidence(out)
    prs = sorted(
        (normalize(node) for node in fetch_pull_requests(repo, start, end, graphql)), key=lambda pr: pr["number"]
    )
    for pr in prs:
        write_json(out / "evidence" / f"{pr['number']}.json", pr)
    index = {
        "repository": repo,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "collected_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "pull_requests": [_summary(pr) for pr in prs],
    }
    write_json(out / "index.json", index)
    return index


def default_run_dir(start: date, end: date) -> Path:
    return RUNS_ROOT / f"{start.isoformat()}..{end.isoformat()}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--window", default=load_filters().defaults["window"])
    parser.add_argument("--out", type=Path, help="run folder (default: .review-learning/<start>..<end>)")
    parser.add_argument("--repo", default=REPOSITORY)
    args = parser.parse_args()
    start, end = parse_window(args.window, datetime.now(UTC).date())
    out = args.out or default_run_dir(start, end)
    index = collect(args.repo, start, end, out)
    print(f"{len(index['pull_requests'])} pull requests merged from {start} to {end} -> {out}")


if __name__ == "__main__":
    main()
