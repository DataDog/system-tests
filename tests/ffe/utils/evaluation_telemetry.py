"""Count evaluation telemetry from final Agent captures."""

from collections.abc import Iterable
from typing import Any


def assert_count(actual: float, expected: int, flag: str) -> None:
    assert actual == expected, f"{flag}: expected {expected} evaluations, captured {actual}"


def evaluation_count(captures: Iterable[dict[str, Any]], flag: str) -> int:
    total = 0
    for data in captures:
        content = data.get("request", {}).get("content", {})
        if not isinstance(content, dict):
            continue
        for event in content.get("flagEvaluations", []):
            if event.get("flag", {}).get("key") == flag:
                total += event["evaluation_count"]
    return total
