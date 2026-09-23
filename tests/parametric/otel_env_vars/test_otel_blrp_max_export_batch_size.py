import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI

from .utils import BLRP_LIBRARY_ENV, assert_blrp_configuration


VARIABLE_NAME = "OTEL_BLRP_MAX_EXPORT_BATCH_SIZE"
DEFAULT_VALUE = 512
DEFAULT_QUEUE_SIZE = 2048
STABLE_VALUE = 64
ZERO_VALUE = 0
TOO_LARGE_VALUE = DEFAULT_QUEUE_SIZE + 1


@scenarios.parametric
@features.otel_blrp_max_export_batch_size
class Test_OTEL_BLRP_MAX_EXPORT_BATCH_SIZE:
    @pytest.mark.parametrize(
        ("library_env", "expected_value"),
        [pytest.param({**BLRP_LIBRARY_ENV, VARIABLE_NAME: STABLE_VALUE}, STABLE_VALUE, id="64")],
    )
    def test_stable_value(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        expected_value: int,
    ) -> None:
        assert_blrp_configuration(test_agent, test_library, VARIABLE_NAME, expected_value)

    @pytest.mark.parametrize(
        ("library_env", "expected_value"),
        [pytest.param({**BLRP_LIBRARY_ENV}, DEFAULT_VALUE, id="unset")],
    )
    def test_default_matches_specification(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        expected_value: int,
    ) -> None:
        assert_blrp_configuration(test_agent, test_library, VARIABLE_NAME, expected_value)

    @pytest.mark.parametrize(
        ("library_env", "expected_value"),
        [pytest.param({**BLRP_LIBRARY_ENV, VARIABLE_NAME: ""}, DEFAULT_VALUE, id="empty")],
    )
    def test_empty_is_treated_as_unset(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        expected_value: int,
    ) -> None:
        assert_blrp_configuration(test_agent, test_library, VARIABLE_NAME, expected_value)

    @pytest.mark.parametrize(
        ("library_env", "expected_value"),
        [
            pytest.param({**BLRP_LIBRARY_ENV, VARIABLE_NAME: ZERO_VALUE}, DEFAULT_VALUE, id="zero"),
            pytest.param({**BLRP_LIBRARY_ENV, VARIABLE_NAME: TOO_LARGE_VALUE}, DEFAULT_VALUE, id="greater-than-queue"),
        ],
    )
    def test_invalid_value_is_ignored(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        expected_value: int,
    ) -> None:
        assert_blrp_configuration(test_agent, test_library, VARIABLE_NAME, expected_value)
