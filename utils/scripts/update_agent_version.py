#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


PIN_COMMENT = "Pinned Agent version, updated automatically by APMSP-3752"
PIN_COMMENT_PATTERN = rf"(?:Pin to .* agent release\. APMSP-[0-9]+|{re.escape(PIN_COMMENT)})"
VERSION_PATTERN = re.compile(r"^7\.[0-9]+\.[0-9]+$")

INSTALLER_PROVISION = Path("utils/build/virtual_machine/provisions/auto-inject/auto-inject_installer_manual.yml")
DOCKER_COMPOSE_PROVISION = Path(
    "utils/build/virtual_machine/provisions/auto-inject/docker/docker-compose-agent-prod.yml"
)


def normalize_version(version: str) -> str:
    normalized = version.removeprefix("v")
    if VERSION_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"Expected a stable Agent 7 version, got: {version}")
    return normalized


def _replace_once(path: Path, pattern: re.Pattern[str], replacement: str) -> bool:
    content = path.read_text()
    updated, replacement_count = pattern.subn(replacement, content)
    if replacement_count != 1:
        raise RuntimeError(f"Expected exactly one Agent version pin in {path}, found {replacement_count}")
    if updated == content:
        return False
    path.write_text(updated)
    return True


def update_agent_version(root: Path, version: str) -> bool:
    normalized = normalize_version(version)
    minor_version = normalized.removeprefix("7.")

    installer_changed = _replace_once(
        root / INSTALLER_PROVISION,
        re.compile(
            rf"(?m)^    # {PIN_COMMENT_PATTERN}\n"
            r"    export DD_AGENT_MAJOR_VERSION=[^\n]+\n"
            r"    export DD_AGENT_MINOR_VERSION=[^\n]+$"
        ),
        f"    # {PIN_COMMENT}\n    export DD_AGENT_MAJOR_VERSION=7\n    export DD_AGENT_MINOR_VERSION={minor_version}",
    )
    compose_changed = _replace_once(
        root / DOCKER_COMPOSE_PROVISION,
        re.compile(
            rf"(?m)^    # {PIN_COMMENT_PATTERN}\n"
            r"    image: gcr\.io/datadoghq/agent:[^\n]+$"
        ),
        f"    # {PIN_COMMENT}\n    image: gcr.io/datadoghq/agent:{normalized}",
    )
    return installer_changed or compose_changed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update the Agent version pinned by SSI scenarios")
    parser.add_argument("version", help="Stable Agent 7 version, for example 7.82.3")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    changed = update_agent_version(args.root, args.version)
    print(f"Agent pins {'updated' if changed else 'already current'}: {normalize_version(args.version)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
