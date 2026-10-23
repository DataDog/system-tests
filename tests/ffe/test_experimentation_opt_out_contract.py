"""Check that exposure assertions reject leaks, loss, and duplicate events."""

from pathlib import Path
from copy import deepcopy
import json
import shutil
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

from tests.ffe.utils.experimentation_opt_out import assert_exposures, evaluation_case
from tests.ffe.utils.lean_experimentation_opt_out import (
    FIXTURES,
    assert_details,
    assert_evaluation_delivery,
    load_runtime_cases,
    load_lookup_cases,
)
from utils import HttpResponse, features, pytest, scenarios
from utils.properties_serialization import SetupProperties


@scenarios.feature_flagging_contract_tests
@features.not_reported
@pytest.mark.parametrize(
    ("subjects", "variant", "allocation", "passes"),
    [
        (["allowed"], "on", "experiment", True),
        ([], "on", "experiment", False),
        (["allowed", "excluded"], "on", "experiment", False),
        (["allowed", "allowed"], "on", "experiment", False),
        (["allowed"], "off", "experiment", False),
        (["allowed"], "on", "ordinary", False),
        (["allowed"], "__dd_subject_opt_out", "experiment", False),
    ],
)
def test_experimentation_exposure_oracle(subjects: list[str], variant: str, allocation: str, *, passes: bool) -> None:
    events = [
        {
            "flag": {"key": "flag"},
            "subject": {"id": subject},
            "variant": {"key": variant},
            "allocation": {"key": allocation},
        }
        for subject in subjects
    ]
    captures: list[dict[str, Any]] = [{"path": "/api/v2/exposures", "request": {"content": {"exposures": events}}}]

    def validate() -> None:
        assert_exposures(captures, flags={"flag"}, expected={("flag", "allowed", "experiment", "on")})

    if passes:
        validate()
    else:
        with pytest.raises(AssertionError, match="Expected exposures"):
            validate()


@scenarios.feature_flagging_contract_tests
@features.not_reported
@pytest.mark.parametrize("shape", ["list", "holdout-groups"])
def test_evaluation_setup_replay(tmp_path: Path, shape: str) -> None:
    case = evaluation_case(
        "flag", "subject", {"dd_experimentation_opt_out_at": "2026-02-01T00:00:00Z"}, "on", exposure=True
    )
    response = HttpResponse(
        {
            "request": {"method": "POST", "url": "http://weblog/ffe", "params": None},
            "status_code": 200,
            "text": '{"value": "on"}',
            "cookies": {},
        }
    )
    case["responses"].append(response)
    cases = [case] if shape == "list" else {"older": [case]}
    source = Mock(nodeid="test-case", instance=SimpleNamespace(cases=cases))
    store = SetupProperties()
    store.store_properties(source)
    store.dump(str(tmp_path))

    replay = SetupProperties()
    replay.load(str(tmp_path))
    target = Mock(nodeid="test-case", instance=SimpleNamespace())
    replay.restore_properties(target)
    restored = target.instance.cases[0] if shape == "list" else target.instance.cases["older"][0]
    assert {key: value for key, value in restored.items() if key != "responses"} == {
        key: value for key, value in case.items() if key != "responses"
    }
    assert len(restored["responses"]) == 1
    assert restored["responses"][0].status_code == response.status_code
    assert restored["responses"][0].text == response.text


@scenarios.feature_flagging_contract_tests
@features.not_reported
def test_lean_runtime_inventory() -> None:
    cases = load_runtime_cases()
    assert len(cases) == 252
    lookup = load_lookup_cases()
    assert len(lookup) == 9
    assert {case["expected"]["errorCode"] for case in lookup} == {"INVALID_CONTEXT", "FLAG_NOT_FOUND"}
    for mode in ["disabled", "immediate", "future_experiments_only"]:
        selected = [case for case in cases if case["mode"] == mode]
        assert len(selected) == 84
        assert len([case for case in lookup if case["mode"] == mode]) == 3
        assert len({case["oracle_case_id"] for case in selected}) == 30
    # Full oracle identity survives materialization; error and fallback values
    # cannot distinguish these cases without the public detail assertions.
    assert {case["expected"]["errorCode"] for case in cases} == {None, "INVALID_CONTEXT", "PARSE_ERROR"}
    assert {case["expected"]["value"] for case in cases} == {"same-value"}


@scenarios.feature_flagging_contract_tests
@features.not_reported
@pytest.mark.parametrize(
    "name",
    [
        "runtime-cases.json",
        "policy-oracle.jsonl",
        "lean/Contract.lean",
        "SOURCE.json",
        "lookup-cases.json",
        "lean/Review.lean",
        "lean/LookupOracle.lean",
    ],
)
def test_lean_runtime_rejects_changed_snapshot(tmp_path: Path, name: str) -> None:
    snapshot = tmp_path / "snapshot"
    shutil.copytree(FIXTURES, snapshot)
    changed = snapshot / name
    changed.write_bytes(changed.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Changed Lean runtime fixture|Unreviewed Lean runtime source manifest"):
        load_runtime_cases(snapshot)


@scenarios.feature_flagging_contract_tests
@features.not_reported
@pytest.mark.parametrize("field", ["value", "reason", "errorCode", "variant", "allocationKey", "count"])
def test_lean_details_reject_wrong_observation(field: str) -> None:
    case = next(case for case in load_runtime_cases() if case["id"] == "policy/immediate/valid/before/1/fallback")
    expected = case["expected"]
    actual = {key: value for key, value in expected.items() if key != "exposure"}
    actual.update(count=1, flagMetadata={})

    def response(body: dict[str, Any]) -> HttpResponse:
        return HttpResponse(
            {
                "request": {"method": "POST", "url": "http://weblog/ffe", "params": None},
                "status_code": 200,
                "text": json.dumps(body),
                "cookies": {},
            }
        )

    assert_details([response(actual)], case, expected_count=1)
    incorrect = deepcopy(actual)
    incorrect[field] = 2 if field == "count" else "wrong"
    with pytest.raises(AssertionError):
        assert_details([response(incorrect)], case, expected_count=1)


@scenarios.feature_flagging_contract_tests
@features.not_reported
@pytest.mark.parametrize("mutation", ["missing", "wrong-subject", "suppression-leak", "duplicate", "wrong-count"])
def test_lean_evaluation_delivery_negative_controls(mutation: str) -> None:
    cases: list[dict[str, Any]] = [
        {"flag": "flag", "subject": "observed", "expected_evaluations": 3},
        {"flag": "flag", "subject": "suppressed", "expected_evaluations": 0},
    ]
    event: dict[str, Any] = {"flag": {"key": "flag"}, "subject": {"id": "observed"}, "evaluation_count": 3}
    content: dict[str, Any] = {"flagEvaluations": [event]}
    captures: list[dict[str, Any]] = [{"request": {"content": content}}]
    assert_evaluation_delivery(captures, cases)
    if mutation == "missing":
        content["flagEvaluations"] = []
    elif mutation == "wrong-subject":
        event["subject"]["id"] = "suppressed"
    elif mutation == "suppression-leak":
        content["flagEvaluations"].append({**event, "subject": {"id": "suppressed"}})
    elif mutation == "duplicate":
        content["flagEvaluations"].append(deepcopy(event))
    else:
        event["evaluation_count"] = 2
    with pytest.raises(AssertionError):
        assert_evaluation_delivery(captures, cases)
