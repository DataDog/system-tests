"""Step 3a: build the batches that the extract model reads.

Usage:
    python3 -m utils.scripts.review_learning.prepare --run .review-learning/run

Reads filtered.json and fixes.json. Keeps only the pull requests with a signal: a human comment,
or a fix with a culprit. Writes batches/batch-<n>.txt and batches/manifest.json.

Each batch wraps its JSON in <untrusted_pr_data_<nonce>> tags. The nonce is random for each run,
so text inside a pull request cannot close the block. The tags come from prlore
(src/util/untrusted.ts).
"""

from __future__ import annotations

import argparse
import json
import secrets
from pathlib import Path
from typing import TYPE_CHECKING

from utils.scripts.review_learning import szz
from utils.scripts.review_learning.common import CommandError, read_json, run, write_json

if TYPE_CHECKING:
    from utils.scripts.review_learning.common import Json

BATCH_SIZE = 10
MAX_FILES = 30
MAX_HUNK_CHARS = 600
MAX_DIFF_CHARS = 3000


def _shorten(text: str | None, limit: int) -> str | None:
    return text if text is None or len(text) <= limit else text[:limit] + " [...]"


def _comment(comment: Json) -> Json:
    author = comment["author"]
    return {
        "url": comment["url"],
        "author": author["login"],
        "association": author["association"],
        "body": comment["body"],
    }


def _thread(thread: Json) -> Json:
    return {
        "path": thread["path"],
        "outcome": thread["outcome"],
        "diff_hunk": _shorten(thread["comments"][0]["diff_hunk"], MAX_HUNK_CHARS),
        "comments": [_comment(comment) for comment in thread["comments"]],
    }


def fix_diff(fix: Json, merge_commit: str | None, root: Path) -> str | None:
    sha = merge_commit or szz.find_pr_commit(fix["fix_pr"], root)
    if not sha:
        return None
    try:
        diff = run(["git", "diff", "--no-ext-diff", "--no-textconv", "--stat", "-p", f"{sha}^", sha], cwd=root)
    except CommandError:
        return None
    return _shorten(diff, MAX_DIFF_CHARS)


def _fix(fix: Json, pr: Json, root: Path) -> Json:
    return {
        "culprits": [{"pr": c["pr"], "signal": c["signal"], "files": c["files"][:MAX_FILES]} for c in fix["culprits"]],
        "absence": fix["absence"],
        "missing_in_culprit": fix["missing_in_culprit"],
        "diff": fix_diff(fix, pr.get("merge_commit"), root),
    }


def compact(pr: Json, fix: Json | None, root: Path) -> Json:
    """Keep what the model needs to judge the pull request, and nothing else."""
    reviews = [r for r in pr["reviews"] if r["body"].strip()]
    return {
        "pr": pr["number"],
        "title": pr["title"],
        "author": pr["author"]["login"],
        "body": pr["body"],
        "files": [file["path"] for file in pr["files"]][:MAX_FILES],
        "threads": [_thread(thread) for thread in pr["threads"]],
        "comments": [_comment(comment) for comment in pr["comments"] + reviews],
        "fix": _fix(fix, pr, root) if fix and "culprits" in fix else None,
    }


def has_signal(item: Json) -> bool:
    return bool(item["threads"] or item["comments"] or item["fix"])


def wrap(batch: list[Json], nonce: str) -> str:
    data = json.dumps(batch, indent=1, ensure_ascii=False)
    return f"<untrusted_pr_data_{nonce}>\n{data}\n</untrusted_pr_data_{nonce}>\n"


def write_batches(out: Path, batches: list[list[Json]], nonce: str) -> list[Json]:
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("batch-*.txt"):
        old.unlink()
    files = []
    for number, batch in enumerate(batches, start=1):
        path = out / f"batch-{number:02d}.txt"
        path.write_text(wrap(batch, nonce), encoding="utf-8")
        files.append({"file": path.name, "prs": [item["pr"] for item in batch]})
    return files


def clear_model_outputs(run_dir: Path) -> None:
    """New batches make the outputs of the later steps stale, so delete them."""
    stale = [*(run_dir / "candidates").glob("*.json"), *(run_dir / "proposals").glob("*.json")]
    stale += [
        run_dir / name for name in ("verified.json", "unverified.json", "lint.json", "decisions.json", "report.md")
    ]
    for path in stale:
        path.unlink(missing_ok=True)


def prepare(run_dir: Path, root: Path) -> Json:
    fixes = {fix["fix_pr"]: fix for fix in read_json(run_dir / "fixes.json")}
    items = [compact(pr, fixes.get(pr["number"]), root) for pr in read_json(run_dir / "filtered.json")]
    items = [item for item in items if has_signal(item)]
    nonce = secrets.token_hex(8)
    batches = [items[i : i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
    clear_model_outputs(run_dir)
    manifest = {"nonce": nonce, "batches": write_batches(run_dir / "batches", batches, nonce)}
    write_json(run_dir / "batches" / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    manifest = prepare(args.run, args.repo_root)
    prs = sum(len(batch["prs"]) for batch in manifest["batches"])
    print(f"{prs} pull requests with a signal in {len(manifest['batches'])} batches -> {args.run / 'batches'}")


if __name__ == "__main__":
    main()
