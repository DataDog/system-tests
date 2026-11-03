"""Fail CI when a pull request introduces a manifest YAML scalar value that contains a
YAML-special character without quoting it.

Per `.cursor/rules/pr-review.mdc` rule 11 ("Manifest YAML Syntax"), manifest values
containing special YAML characters (``<``, ``>``, ``#``, ``:``) must be quoted, since an
unquoted plain scalar beginning with (or containing) one of these characters can be
misparsed by YAML tooling, or silently truncated at a `#` comment marker. This pattern
has been flagged repeatedly in code review (unquoted `component_version` ranges such as
`<3.57.0`, and unquoted `missing_feature (...)` reasons containing `#`).

This script only checks lines *added or modified* by the current pull request (via `git
diff` against the PR base) so the pre-existing unquoted values already in
`manifests/*.yml` do not block unrelated PRs -- it only stops new violations from being
introduced.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml

MANIFEST_DIR = Path("manifests")
SPECIAL_CHARS = ("<", ">", "#", ":")


def _changed_line_numbers(base: str, path: Path) -> set[int]:
    """Return the set of line numbers added/modified by the diff for `path`, relative
    to the new (post-change) version of the file.
    """
    result = subprocess.run(
        ["git", "diff", "-U0", f"{base}...HEAD", "--", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # e.g. the base ref isn't reachable; don't block CI on a diff infra failure,
        # the full-history `format.sh` / manifest validation checks already cover syntax.
        return set()

    changed: set[int] = set()
    current_line = 0
    for line in result.stdout.splitlines():
        if line.startswith("@@"):
            # Hunk header: "@@ -a,b +c,d @@ ..."
            plus_part = line.split("+", 1)[1].split(" ", 1)[0]
            current_line = int(plus_part.split(",")[0])
        elif line.startswith("+") and not line.startswith("+++"):
            changed.add(current_line)
            current_line += 1
        # "-" lines (removals) don't correspond to a line number in the new file and
        # are skipped; with -U0 there are no unchanged context lines to account for.

    return changed


def _unquoted_special_char_scalars(path: Path) -> list[tuple[int, str]]:
    """Return (line, value) for every plain-style scalar value under the top-level
    `manifest:` key that contains a YAML-special character.
    """
    with open(path, encoding="utf-8") as f:
        root = yaml.compose(f, Loader=yaml.SafeLoader)

    if root is None or not isinstance(root, yaml.MappingNode):
        return []

    errors: list[tuple[int, str]] = []

    def walk_value(node: yaml.Node) -> None:
        if isinstance(node, yaml.ScalarNode):
            if node.style not in ("'", '"') and any(ch in node.value for ch in SPECIAL_CHARS):
                errors.append((node.start_mark.line + 1, node.value))
        elif isinstance(node, yaml.MappingNode):
            for _key_node, value_node in node.value:
                walk_value(value_node)
        elif isinstance(node, yaml.SequenceNode):
            for item in node.value:
                walk_value(item)

    for key_node, value_node in root.value:
        if key_node.value == "manifest":
            walk_value(value_node)

    return errors


def _resolve_base(explicit_base: str | None) -> str | None:
    """Resolve the git ref to diff against.

    Priority: an explicit --base argument, then the $GITHUB_BASE_SHA env var (set by
    CI to the pull request's base commit), then a local merge-base with origin/main
    (useful when running `./format.sh` on a local branch). Returns None if nothing
    usable could be resolved, in which case the check is skipped rather than failing
    CI on unrelated infrastructure issues.
    """
    if explicit_base:
        return explicit_base

    env_base = os.environ.get("GITHUB_BASE_SHA")
    if env_base:
        return env_base

    result = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/main"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default=None,
        help=(
            "Base git ref/sha to diff against (the PR base). If omitted, falls back to "
            "$GITHUB_BASE_SHA, then to a local merge-base with origin/main."
        ),
    )
    args = parser.parse_args()

    base = _resolve_base(args.base)
    if base is None:
        print(  # noqa: T201 -- CLI diagnostic output, mirrors format.py/validate.py in this package
            "Manifest YAML quoting check: could not resolve a base ref to diff against, skipping."
        )
        return 0

    had_errors = False
    for path in sorted(MANIFEST_DIR.glob("*.yml")):
        changed_lines = _changed_line_numbers(base, path)
        if not changed_lines:
            continue

        for line_no, value in _unquoted_special_char_scalars(path):
            if line_no in changed_lines:
                had_errors = True
                print(  # noqa: T201 -- CLI diagnostic output, mirrors format.py/validate.py in this package
                    f"{path}:{line_no}: value {value!r} contains a YAML-special character "
                    f"({'/'.join(SPECIAL_CHARS)}) and must be quoted "
                    "(see .cursor/rules/pr-review.mdc, rule 11: Manifest YAML Syntax)"
                )

    if had_errors:
        print("\nManifest YAML quoting check failed. Please fix the errors above. 💥 💔 💥")  # noqa: T201
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
