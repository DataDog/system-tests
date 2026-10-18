"""Validate evaluation responses and telemetry after the scenario stops."""

import json
from collections.abc import Iterable
from typing import Any

from utils import HttpResponse


def assert_evaluation_responses(responses: list[HttpResponse], *, expected_count: int, expected_value: str) -> None:
    assert len(responses) == expected_count, f"Expected {expected_count} evaluation responses, got {len(responses)}"
    for response in responses:
        assert response.status_code == 200, response.text
        assert json.loads(response.text)["value"] == expected_value, response.text


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
