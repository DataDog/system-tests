from __future__ import annotations

import difflib
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
AGENTS_PATH = ROOT / "AGENTS.md"
CLAUDE_PATH = ROOT / "CLAUDE.md"
CLAUDE_COMMENT = (
    "<!-- This file is generated from AGENTS.md. Rule links become Claude @ imports, and AGENTS.md filename "
    "references become CLAUDE.md. Edit AGENTS.md and run ./format.sh to regenerate this file. -->"
)
RULE_LINK_PATTERN = re.compile(r"\[[^\]]+\]\((\.agents/rules/[^)]+)\)")


def _replace_rule_link(match: re.Match[str]) -> str:
    return f"@./{match.group(1)}"


def _expected_claude_content(agents_content: str) -> str:
    content = f"{agents_content.rstrip()}\n"
    content = content.replace("# AGENTS.md -", "# CLAUDE.md -", 1)
    content = content.replace("`AGENTS.md`", "`CLAUDE.md`")
    content = RULE_LINK_PATTERN.sub(_replace_rule_link, content)
    return f"{CLAUDE_COMMENT}\n\n{content}"


def main(arguments: list[str]) -> int:
    if len(arguments) > 1 or (arguments and arguments[0] not in {"--check", "--fix"}):
        sys.stderr.write("Usage: python utils/scripts/check_agent_instructions.py [--check|--fix]\n")
        return 2

    mode = arguments[0] if arguments else "--check"
    expected = _expected_claude_content(AGENTS_PATH.read_text(encoding="utf-8"))
    actual = CLAUDE_PATH.read_text(encoding="utf-8") if CLAUDE_PATH.exists() else ""

    if mode == "--fix":
        if actual != expected:
            CLAUDE_PATH.write_text(expected, encoding="utf-8")
            print("Updated CLAUDE.md from AGENTS.md")
        return 0

    if actual == expected:
        return 0

    diff = difflib.unified_diff(
        actual.splitlines(keepends=True),
        expected.splitlines(keepends=True),
        fromfile=str(CLAUDE_PATH.relative_to(ROOT)),
        tofile=f"{CLAUDE_PATH.relative_to(ROOT)} (expected)",
    )
    sys.stderr.write("CLAUDE.md is not synchronized with AGENTS.md:\n")
    sys.stderr.writelines(diff)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
