"""Check that exposure assertions reject leaks, loss, and duplicate events."""

from typing import Any

from tests.ffe.utils.experimentation_opt_out import assert_exposures
from utils import features, pytest, scenarios


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
