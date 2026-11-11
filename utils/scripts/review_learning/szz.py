"""Find, for each fix pull request, the earlier pull request that introduced the defect (SZZ).

Uses the local Git history only: system-tests squash-merges, so each commit on main ends with
"(#<number>)". Three signals, from the most to the least reliable:
1. revert: the fix reverts a commit.
2. link: the title or the body names the earlier pull request ("follow-up to #123").
3. blame: git blame finds the commits that last changed the lines that the fix changes.

Adapted from sphinx (jb-claude-marketplace, skills/sphinx/scripts/szz_core.py): the blame loop
that skips non-semantic commits (_blame_line), and the anchor on the line above each insertion
for a file with only additions (_extract_changed_lines). Changes from sphinx:
- It blames every text file, also YAML, shell, and Dockerfiles: manifests and scripts hold many
  system-tests defects.
- It skips only conventional-commit prefixes, and it follows the line number across blame hops.
- It finds reverts and explicit links before it uses the blame.

Usage:
    python3 -m utils.scripts.review_learning.szz --run .review-learning/run
    python3 -m utils.scripts.review_learning.szz --fix-pr 8371
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from utils.scripts.review_learning.common import CommandError, load_filters, matches_any, read_json, run, write_json

if TYPE_CHECKING:
    from collections.abc import Iterator

    from utils.scripts.review_learning.common import Json

MAX_HOPS = 5
MAX_FILES = 10
MAX_LINES_PER_FILE = 5

# Only conventional-commit prefixes and merges: a subject such as "Fix the build for Java 21" is semantic.
NON_SEMANTIC = re.compile(
    r"^((build|ci|docs?|chore|style)(\([^)]*\))?!?:|merge (branch|pull request)\b)", re.IGNORECASE
)
FIX_TITLE = re.compile(r"^\s*(revert\b|fix(es|ed)?\b|fix\(|hotfix\b|follow[- ]?up\b)", re.IGNORECASE)
LINK = re.compile(
    r"(follow[- ]?up (?:to|of|for|on)|fix(?:es|ed)? (?:for|from)|regression (?:from|in|of)|introduced (?:in|by)|"
    r"broken (?:in|by)|reverts?)\s+(?:#|https://github\.com/DataDog/system-tests/pull/)(\d+)",
    re.IGNORECASE,
)
REVERTED_SHA = re.compile(r"This reverts commit ([0-9a-f]{7,40})", re.IGNORECASE)
REVERTS_PR = re.compile(r"\bReverts (?:DataDog/system-tests)?#(\d+)", re.IGNORECASE)
REVERT_TITLE = re.compile(r'^Revert "(.+)"')
PR_SUFFIX = re.compile(r"\(#(\d+)\)\s*$")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


@dataclass(frozen=True)
class FileChange:
    """Old-file lines to blame for one file of a fix."""

    path: str
    lines: tuple[int, ...]
    additions_only: bool


def is_fix_candidate(title: str, body: str) -> bool:
    text = f"{title}\n{body}"
    return bool(FIX_TITLE.search(title) or LINK.search(text) or REVERTED_SHA.search(body) or REVERTS_PR.search(body))


def linked_prs(title: str, body: str) -> list[int]:
    return sorted({int(number) for _, number in LINK.findall(f"{title}\n{body}")})


def pr_from_subject(subject: str) -> int | None:
    match = PR_SUFFIX.search(subject)
    return int(match.group(1)) if match else None


def diff_hunks(diff: str) -> Iterator[tuple[str, int, int]]:
    """Yield (path, first old line, old line count) for each hunk of a 'git diff -U0'. New files have no old path."""
    path: str | None = None
    in_header = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            path, in_header = None, True
        elif in_header and line.startswith("--- "):
            path = line[6:] if line.startswith("--- a/") else None
        elif path and (match := HUNK.match(line)):
            in_header = False
            yield path, int(match.group(1)), int(match.group(2) or "1")


def parse_diff(diff: str) -> list[FileChange]:
    """Return, per file, the deleted lines, or the line above each insertion when the file has only additions."""
    deleted: dict[str, set[int]] = {}
    anchors: dict[str, set[int]] = {}
    for path, start, count in diff_hunks(diff):
        if count:
            deleted.setdefault(path, set()).update(range(start, start + count))
        else:
            anchors.setdefault(path, set()).add(max(start, 1))
    additions = {path: lines for path, lines in anchors.items() if path not in deleted}
    return _file_changes(deleted, additions_only=False) + _file_changes(additions, additions_only=True)


def _file_changes(lines_by_path: dict[str, set[int]], *, additions_only: bool) -> list[FileChange]:
    return [
        FileChange(path, tuple(sorted(lines))[:MAX_LINES_PER_FILE], additions_only=additions_only)
        for path, lines in lines_by_path.items()
    ]


def blame_line(sha: str, path: str, line: int, root: Path) -> str | None:
    """Return the commit that last changed this line before sha, skipping non-semantic commits."""
    current, blamed = f"{sha}^", None
    for _ in range(MAX_HOPS):
        try:
            output = run(["git", "blame", "--porcelain", "-L", f"{line},{line}", current, "--", path], cwd=root)
        except CommandError:
            return blamed
        blamed, line, path = parse_blame(output)
        if not NON_SEMANTIC.search(subject(blamed, root)):
            return blamed
        current = f"{blamed}^"
    return blamed


def parse_blame(porcelain: str) -> tuple[str, int, str]:
    """Return the blamed commit, and the line number and path of the line in that commit."""
    lines = porcelain.splitlines()
    sha, original_line = lines[0].split()[:2]
    path = next(line[len("filename ") :] for line in lines if line.startswith("filename "))
    return sha, int(original_line), path


def commit_exists(sha: str, root: Path) -> bool:
    try:
        run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=root)
    except CommandError:
        return False
    return True


@cache
def subject(sha: str, root: Path) -> str:
    return run(["git", "log", "-1", "--format=%s", sha], cwd=root).strip()


def changed_files(sha: str, root: Path) -> set[str]:
    return set(run(["git", "show", "--no-renames", "--name-only", "--format=", sha], cwd=root).split())


@cache
def find_pr_commit(pr: int, root: Path) -> str | None:
    """Return the squash commit of a pull request on the first-parent history of HEAD."""
    output = run(["git", "log", "--first-parent", "--format=%H %s", "-E", f"--grep=\\(#{pr}\\)$", "HEAD"], cwd=root)
    for line in output.splitlines():
        sha, _, title = line.partition(" ")
        if pr_from_subject(title) == pr:
            return sha
    return None


def reverted_pr(title: str, body: str, root: Path) -> int | None:
    """Return the reverted pull request, from 'Reverts DataDog/system-tests#N', the reverted commit, or the title."""
    if match := REVERTS_PR.search(body):
        return int(match.group(1))
    try:
        if match := REVERTED_SHA.search(body):
            return pr_from_subject(subject(match.group(1), root))
        if match := REVERT_TITLE.match(title):
            return pr_from_title(match.group(1), root)
    except CommandError:
        return None
    return None


def pr_from_title(title: str, root: Path) -> int | None:
    """Return the pull request whose squash commit starts with this title."""
    output = run(["git", "log", "--first-parent", "--format=%s", "-F", f"--grep={title}", "HEAD"], cwd=root)
    for line in output.splitlines():
        if line.startswith(title) and (number := pr_from_subject(line)):
            return number
    return None


def blame_fix(sha: str, root: Path, skip_paths: tuple[str, ...]) -> tuple[Counter[int], list[FileChange]]:
    """Count, per earlier pull request, the blamed lines of the fix."""
    diff = run(
        ["git", "diff", "--no-ext-diff", "--no-textconv", "--src-prefix=a/", "--dst-prefix=b/", "-U0", f"{sha}^", sha],
        cwd=root,
    )
    changes = [c for c in parse_diff(diff) if not matches_any(c.path, skip_paths)][:MAX_FILES]
    culprits: Counter[int] = Counter()
    for change in changes:
        for line in change.lines:
            blamed = blame_line(sha, change.path, line, root)
            if blamed and (number := pr_from_subject(subject(blamed, root))):
                culprits[number] += 1
    return culprits, changes


def _culprit(number: int, signal: str, lines: int, root: Path) -> Json:
    sha = find_pr_commit(number, root)
    return {
        "pr": number,
        "signal": signal,
        "blamed_lines": lines,
        "files": sorted(changed_files(sha, root)) if sha else [],
    }


def find_culprits(pr: Json, blamed: Counter[int], root: Path) -> list[Json]:
    """Order the culprits by signal: the reverted pull request, then linked ones, then the blamed ones."""
    reverted = reverted_pr(pr["title"], pr["body"], root)
    numbers = [(reverted, "revert")] if reverted else []
    numbers += [(n, "link") for n in linked_prs(pr["title"], pr["body"])]
    numbers += [(n, "blame") for n, _ in blamed.most_common()]
    culprits: list[Json] = []
    for number, signal in numbers:
        if number != pr["number"] and number not in {c["pr"] for c in culprits}:
            culprits.append(_culprit(number, signal, blamed.get(number, 0), root))
    return culprits


def absence(changes: list[FileChange], culprit: Json) -> Json:
    """The fix adds what the culprit left out: it only adds lines, or it changes files that the culprit did not."""
    # Without the culprit's files, a missing file cannot be told apart from an unknown one.
    missing = sorted({change.path for change in changes} - set(culprit["files"])) if culprit["files"] else []
    additions_only = bool(changes) and all(change.additions_only for change in changes)
    return {"absence": additions_only or bool(missing), "additions_only": additions_only, "missing_in_culprit": missing}


def analyse_fix(pr: Json, root: Path, skip_paths: tuple[str, ...]) -> Json | None:
    """Return the culprits of a fix pull request, or None when it is not a fix or has no culprit."""
    if not is_fix_candidate(pr["title"], pr["body"]):
        return None
    sha = pr.get("merge_commit") or find_pr_commit(pr["number"], root)
    if not sha or not commit_exists(sha, root):
        return {
            "fix_pr": pr["number"],
            "title": pr["title"],
            "error": "merge commit not found locally; run git fetch origin main",
        }
    blamed, changes = blame_fix(sha, root, skip_paths)
    culprits = find_culprits(pr, blamed, root)
    if not culprits:
        return None
    return {"fix_pr": pr["number"], "title": pr["title"], "culprits": culprits, **absence(changes, culprits[0])}


def analyse_run(run_dir: Path, root: Path) -> list[Json]:
    skip_paths = load_filters().skip_blame_paths
    fixes = [analyse_fix(pr, root, skip_paths) for pr in read_json(run_dir / "filtered.json")]
    found = [fix for fix in fixes if fix is not None]
    write_json(run_dir / "fixes.json", found)
    return found


def _pr_from_git(number: int, root: Path) -> Json:
    sha = find_pr_commit(number, root)
    if not sha:
        raise SystemExit(f"no commit ending with (#{number}) on the first-parent history of HEAD")
    message = run(["git", "log", "-1", "--format=%B", sha], cwd=root)
    title, _, body = message.partition("\n")
    return {"number": number, "title": title, "body": body, "merge_commit": sha}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", type=Path, help="analyse every pull request of filtered.json")
    group.add_argument("--fix-pr", type=int, help="analyse one pull request, read from the local Git history")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if args.run:
        fixes = analyse_run(args.run, args.repo_root)
        print(f"{len(fixes)} fix pull requests with a culprit -> {args.run / 'fixes.json'}")
    else:
        pr = _pr_from_git(args.fix_pr, args.repo_root)
        result = analyse_fix(pr, args.repo_root, load_filters().skip_blame_paths)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
