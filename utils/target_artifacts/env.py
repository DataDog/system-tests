from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


QUOTED_VALUE_MIN_LENGTH = 2


def _parse_dotenv_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    if key.startswith("export "):
        key = key.removeprefix("export ").strip()
    if not key:
        return None

    value = value.strip()
    if len(value) >= QUOTED_VALUE_MIN_LENGTH and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        item = _parse_dotenv_line(line)
        if item is not None:
            key, value = item
            result[key] = value
    return result


def load_environment(repo_root: Path, process_env: dict[str, str]) -> dict[str, str]:
    result = read_dotenv(repo_root / ".env")
    result.update(process_env)
    return result
