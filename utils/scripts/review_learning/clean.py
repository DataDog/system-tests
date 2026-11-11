"""Delete old run folders under .review-learning/.

Usage:
    python3 -m utils.scripts.review_learning.clean            # keep the 3 newest runs
    python3 -m utils.scripts.review_learning.clean --keep 1
    python3 -m utils.scripts.review_learning.clean --all
    python3 -m utils.scripts.review_learning.clean --dry-run

A run folder is a direct subfolder of .review-learning/ that holds an index.json.
The script never deletes anything else, and it never follows a symbolic link.
"""

from __future__ import annotations

import argparse
import shutil
from typing import TYPE_CHECKING

from utils.scripts.review_learning.common import RUNS_ROOT, read_json

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_KEEP = 3


def find_runs(root: Path) -> list[Path]:
    """Return the run folders, the newest first."""
    if not root.is_dir():
        return []
    runs = [
        path for path in root.iterdir() if path.is_dir() and not path.is_symlink() and (path / "index.json").is_file()
    ]
    return sorted(runs, key=lambda path: read_json(path / "index.json")["collected_at"], reverse=True)


def clean(root: Path, keep: int, *, dry_run: bool) -> list[Path]:
    """Delete every run folder except the `keep` newest ones, and return the deleted folders."""
    if keep < 0:
        raise ValueError("keep must be 0 or more")
    old_runs = find_runs(root)[keep:]
    if not dry_run:
        for path in old_runs:
            shutil.rmtree(path)
    return old_runs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--keep", type=int, default=DEFAULT_KEEP, help="number of newest runs to keep")
    group.add_argument("--all", action="store_true", help="delete every run")
    parser.add_argument("--dry-run", action="store_true", help="list the runs to delete, and delete nothing")
    args = parser.parse_args()
    deleted = clean(RUNS_ROOT, 0 if args.all else args.keep, dry_run=args.dry_run)
    verb = "Would delete" if args.dry_run else "Deleted"
    for path in deleted:
        print(f"{verb} {path}")
    print(f"{verb} {len(deleted)} run folders under {RUNS_ROOT}")


if __name__ == "__main__":
    main()
