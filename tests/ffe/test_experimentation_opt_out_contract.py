"""Check that exposure assertions reject leaks, loss, and duplicate events."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

from tests.ffe.utils.experimentation_opt_out import assert_exposures, evaluation_case
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
