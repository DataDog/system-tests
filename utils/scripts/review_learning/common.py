"""Helpers shared by the review-learning steps: configuration, JSON files, and commands."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

Json = dict[str, Any]

FILTERS_PATH = Path(__file__).with_name("filters.yml")
REPOSITORY = "DataDog/system-tests"
RUNS_ROOT = Path(".review-learning")  # It ignores itself, see ignore_runs_root(). clean.py deletes old runs.


class CommandError(RuntimeError):
    """A command returned a non-zero exit code."""


@dataclass(frozen=True)
class AuthorFilter:
    """Who and what to ignore."""

    author_types: tuple[str, ...]
    authors: tuple[str, ...]

    def matches(self, author: Json) -> bool:
        return author["type"] in self.author_types or matches_any(author["login"], self.authors)


@dataclass(frozen=True)
class Filters:
    """The content of filters.yml."""

    defaults: Json
    pr_authors: AuthorFilter
    pr_title_patterns: tuple[str, ...]
    pr_labels: tuple[str, ...]
    pr_numbers: tuple[int, ...]
    comment_authors: AuthorFilter
    comment_body_patterns: tuple[str, ...]
    skip_blame_paths: tuple[str, ...]


def load_filters(path: Path = FILTERS_PATH) -> Filters:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    prs = data["exclude_prs"]
    comments = data["ignore_comments"]
    return Filters(
        defaults=data["defaults"],
        pr_authors=AuthorFilter(tuple(prs["author_types"]), tuple(prs["authors"])),
        pr_title_patterns=tuple(prs["title_patterns"]),
        pr_labels=tuple(prs["labels"]),
        pr_numbers=tuple(prs["numbers"]),
        comment_authors=AuthorFilter(tuple(comments["author_types"]), tuple(comments["authors"])),
        comment_body_patterns=tuple(comments["body_patterns"]),
        skip_blame_paths=tuple(data["skip_blame_paths"]),
    )


def ignore_runs_root(root: Path = RUNS_ROOT) -> None:
    """Make Git ignore the runs folder from inside, as .pytest_cache does. The repository .gitignore stays as it is."""
    root.mkdir(parents=True, exist_ok=True)
    ignore = root / ".gitignore"
    if not ignore.is_file():
        ignore.write_text("# Created by review learning. Git ignores this whole folder.\n*\n", encoding="utf-8")


def matches_any(value: str, patterns: Iterable[str]) -> bool:
    """Match the whole value, ignoring case. Only * is a wildcard: "*[bot]" means a literal [bot] suffix."""
    return any(re.fullmatch(_wildcard(pattern), value, re.IGNORECASE | re.DOTALL) for pattern in patterns)


def _wildcard(pattern: str) -> str:
    return ".*".join(re.escape(part) for part in pattern.split("*"))


def run(args: Sequence[str], cwd: Path | None = None) -> str:
    """Run a command without a shell and return its standard output."""
    result = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise CommandError(f"{args[0]} failed with exit code {result.returncode}: {result.stderr.strip()}")
    return result.stdout


def read_json(path: Path) -> Any:  # noqa: ANN401 -- JSON content has no fixed type
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: object) -> None:
    """Write the file, then read it back to make sure that the content is complete."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
    if read_json(path) != json.loads(text):
        raise RuntimeError(f"{path} does not contain what was written")
