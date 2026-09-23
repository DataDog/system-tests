import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI

from .utils import BLRP_LIBRARY_ENV, assert_blrp_configuration


VARIABLE_NAME = "OTEL_BLRP_EXPORT_TIMEOUT"
DEFAULT_VALUE = 30000
STABLE_VALUE = 17000
ZERO_VALUE = 0
INVALID_VALUE = -1


@scenarios.parametric
@features.otel_blrp_export_timeout
class Test_OTEL_BLRP_EXPORT_TIMEOUT:
    @pytest.mark.parametrize(
        ("library_env", "expected_value"),
        [pytest.param({**BLRP_LIBRARY_ENV, VARIABLE_NAME: STABLE_VALUE}, STABLE_VALUE, id="17000")],
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
        [pytest.param({**BLRP_LIBRARY_ENV, VARIABLE_NAME: ZERO_VALUE}, ZERO_VALUE, id="zero")],
    )
    def test_zero_value(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        expected_value: int,
    ) -> None:
        assert_blrp_configuration(test_agent, test_library, VARIABLE_NAME, expected_value)

    @pytest.mark.parametrize(
        ("library_env", "expected_value"),
        [pytest.param({**BLRP_LIBRARY_ENV, VARIABLE_NAME: INVALID_VALUE}, DEFAULT_VALUE, id="negative")],
    )
    def test_invalid_value_is_ignored(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        expected_value: int,
    ) -> None:
        assert_blrp_configuration(test_agent, test_library, VARIABLE_NAME, expected_value)
