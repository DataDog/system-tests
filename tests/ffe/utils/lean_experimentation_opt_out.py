"""Load Lean-generated expectations and validate actual public SDK observations."""

from collections import Counter
from collections.abc import Iterable
import hashlib
import json
from pathlib import Path
from typing import Any

from utils import HttpResponse


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/experimentation-opt-out-lean"
# Independently reviewed pin. Regeneration never rewrites this acceptance value.
SOURCE_SHA256 = "0407fb0330aefbeb086f16784aba0e5629f9e0241e80cd1416308146cbc9679d"


def verify_snapshot(root: Path) -> None:
    source_bytes = (root / "SOURCE.json").read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != SOURCE_SHA256:
        raise ValueError("Unreviewed Lean runtime source manifest")
    source = json.loads(source_bytes)
    for name, expected in source["files"].items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Contract path escapes its snapshot")
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Changed Lean runtime fixture: {name}")


def load_runtime_cases(root: Path = FIXTURES) -> list[dict[str, Any]]:
    verify_snapshot(root)
    cases: list[dict[str, Any]] = json.loads((root / "runtime-cases.json").read_text())
    if len(cases) != 252 or len({case["id"] for case in cases}) != 252:
        raise ValueError("Lean runtime case inventory changed")
    if len({case["oracle_case_id"] for case in cases}) != 90:
        raise ValueError("Lean policy case omitted")
    return cases


def load_lookup_cases(root: Path = FIXTURES) -> list[dict[str, Any]]:
    verify_snapshot(root)
    cases: list[dict[str, Any]] = json.loads((root / "lookup-cases.json").read_text())
    if len(cases) != 9 or len({case["id"] for case in cases}) != 9:
        raise ValueError("Lean lookup case inventory changed")
    return cases


def assert_details(responses: list[HttpResponse], case: dict[str, Any], *, expected_count: int = 3) -> None:
    assert len(responses) == expected_count, (case["id"], "evaluation count", len(responses))
    expected = case["expected"]
    for response in responses:
        assert response.status_code == 200, (case["id"], response.text)
        actual = json.loads(response.text)
        assert actual["value"] == expected["value"], (case["id"], actual)
        assert actual["count"] == 1, (case["id"], actual)
        assert actual["reason"] == expected["reason"], (case["id"], actual)
        assert (actual["errorCode"] or None) == expected["errorCode"], (case["id"], actual)
        assert (actual["variant"] or None) == expected["variant"], (case["id"], actual)
        assert (actual.get("allocationKey") or None) == expected["allocationKey"], (case["id"], actual)
        assert isinstance(actual["flagMetadata"], dict), (case["id"], actual)


def assert_evaluation_delivery(captures: Iterable[dict[str, Any]], cases: list[dict[str, Any]]) -> None:
    """Check exact hashed subjects and counts under the default evaluation-data policy."""
    flags = {case["flag"] for case in cases}
    actual: Counter[tuple[str, str]] = Counter()
    for capture in captures:
        content = capture.get("request", {}).get("content", {})
        if not isinstance(content, dict):
            continue
        for event in content.get("flagEvaluations", []):
            flag = event.get("flag", {}).get("key")
            if flag in flags:
                subject = event.get("targeting_key")
                count = event["evaluation_count"]
                assert type(count) is int, event
                assert count > 0, event
                actual[(flag, subject)] += count
    expected = Counter(
        {
            (case["flag"], "sha256_" + hashlib.sha256(case["subject"].encode()).hexdigest()): case[
                "expected_evaluations"
            ]
            for case in cases
            if case["expected_evaluations"]
        }
    )
    assert actual == expected, f"Expected evaluation delivery {expected}, got {actual}"
