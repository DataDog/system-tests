from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .models import TargetArtifactError
from .orchestrator import stage_target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stage-target-artifacts")
    parser.add_argument("target", help="Target artifact name, such as python, java, or custom")
    parser.add_argument("environment", nargs="?", default="dev", help="dev, prod, or custom")
    parser.add_argument("--binaries-dir", default=os.environ.get("BINARIES_DIR", "binaries"))
    parser.add_argument("--repo-root", default=".")

    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root)
    binaries_dir = Path(args.binaries_dir)

    try:
        stage_target(args.target, args.environment, repo_root=repo_root, binaries_dir=binaries_dir)
    except TargetArtifactError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    return 0
