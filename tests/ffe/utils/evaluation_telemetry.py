"""Validate evaluation responses and telemetry after the scenario stops."""

import json
import traceback
from collections.abc import Callable, Iterable
from typing import Any

from utils import HttpResponse


def evaluation_setup_error(operation: Callable[[], None]) -> str | None:
    """Defer failures as serializable text for validation and replay."""
    try:
        operation()
    except Exception:  # Report setup failures during the test phase.
        return traceback.format_exc()
    return None


def assert_setup_succeeded(error: str | None) -> None:
    assert error is None, f"Evaluation setup failed:\n{error}"


def assert_evaluation_responses(responses: list[HttpResponse], *, expected_count: int, expected_value: str) -> None:
    assert len(responses) == expected_count, f"Expected {expected_count} evaluation responses, got {len(responses)}"
    for response in responses:
        assert response.status_code == 200, response.text
        assert json.loads(response.text)["value"] == expected_value, response.text


def assert_count(actual: float, expected: int, flag: str) -> None:
    assert actual == expected, f"{flag}: expected {expected} evaluations, captured {actual}"


def assert_metric_activity(metrics: Iterable[dict[str, Any]], flag: str, *, suppressed: bool) -> None:
    # Agent series do not retain the source OTel aggregation temporality. Check
    # presence, not a sum that can count repeated cumulative exports twice.
    # EVP assertions separately check exact evaluation counts.
    values = [
        float(point["value"] if isinstance(point, dict) else point[1])
        for metric in metrics
        if metric.get("metric") == "feature_flag.evaluations" and f"feature_flag.key:{flag}" in metric.get("tags", [])
        for point in metric.get("points", [])
    ]
    if suppressed:
        assert all(value == 0 for value in values), f"{flag}: opted-out evaluation emitted metrics: {values}"
    else:
        assert any(value > 0 for value in values), f"{flag}: missing positive-control evaluation metric: {values}"


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
