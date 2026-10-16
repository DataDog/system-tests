"""Read an immutable shared fixture snapshot and compare actual provider details."""

import hashlib
import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures" / "experimentation-opt-out"


def load_contract() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Verify every source blob before loading the shared contract."""
    source = json.loads((FIXTURES / "SOURCE.json").read_text())
    assert source["commit"] == "5e2430d9ad36644e2cecb6a32ddb8d05d7c98ac6"
    for name, expected in source["blobs"].items():
        contents = (FIXTURES / name).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(contents)).encode() + b"\0" + contents).hexdigest()
        assert actual == expected, f"Modified shared fixture: {name}"
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    configurations = {
        item["id"]: json.loads((FIXTURES / item["path"]).read_text()) for item in manifest["configurations"]
    }
    cases: list[dict[str, Any]] = []
    for group in manifest["evaluationCases"]:
        group_cases = json.loads((FIXTURES / group["path"]).read_text())
        assert [case["id"] for case in group_cases] == group["ids"]
        cases.extend(group_cases)
    assert len(cases) == manifest["expectedCounts"]["evaluations"] == 136
    return manifest, configurations, cases


def has_time_boundary(configuration: dict[str, Any], case: dict[str, Any]) -> bool:
    """Time-gated cases require fixed-clock SDK tests or a guarded live runtime."""
    flag = configuration["flags"][case["evaluation"]["flag"]]
    return any(allocation.get("startAt") or allocation.get("endAt") for allocation in flag["allocations"])


def assert_details(result: dict[str, Any], case: dict[str, Any]) -> None:
    """Require assignment identity and metadata, not only an equal value."""
    expected = case["expected"]
    assert result["value"] == expected["value"], (case["id"], result)
    assignment = expected["assignment"]
    if assignment is None:
        assert not result.get("allocationKey"), (case["id"], result)
        assert not result.get("variant"), (case["id"], result)
        assert result.get("serialId") is None, (case["id"], result)
        if expected["outcome"] != "no-assignment":
            assert result.get("errorCode"), (case["id"], result)
        return
    assert not result.get("errorCode"), (case["id"], result)
    assert result.get("reason"), (case["id"], result)
    assert result.get("allocationKey") == assignment["allocationKey"], (case["id"], result)
    assert result.get("variant") == assignment["variationKey"], (case["id"], result)
    assert result.get("serialId") == assignment["serialId"], (case["id"], result)
    metadata = result.get("flagMetadata", {})
    assert metadata.get("__dd_do_log") is assignment["doLog"], (case["id"], result)
    expected_features = {
        "__dd_feature." + feature["key"]: feature["value"]
        for feature in assignment.get("features", [])
        if "HOOK" in feature["destinations"]
    }
    actual_features = {key: value for key, value in metadata.items() if key.startswith("__dd_feature.")}
    assert actual_features == expected_features, (case["id"], actual_features, expected_features)
