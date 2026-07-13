"""Parametric contract for startup-only offline UFC configuration.

Offline mode receives UFC JSON bytes through the provider API. It must preserve
the same evaluation semantics as Agent RC and agentless delivery while making
no configuration request and accepting no runtime update.
"""

import time
from typing import Any

import pytest

from tests.parametric.conftest import APMLibrary
from tests.parametric.test_ffe.utils import (
    ALL_TEST_CASE_FILES,
    MALFORMED_UFC_BYTES,
    UFC_FIXTURE_BYTES,
    assert_evaluation_cases,
    evaluate_with_configuration_retry,
)
from utils import features, scenarios
from utils.dd_constants import Capabilities
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures._mock_ffe_agentless_backend import MockFFEAgentlessBackendServer

parametrize = pytest.mark.parametrize
pytest_plugins = ["utils.docker_fixtures._mock_ffe_agentless_backend"]

OFFLINE_OBSERVATION_INTERVAL_SECONDS = 0.2
OFFLINE_OBSERVATION_ATTEMPTS = 5
TEST_API_KEY = "system-tests-mock-api-key"

EVALUATION_CASE: dict[str, Any] = {
    "flag": "new-user-onboarding",
    "variation_type": "STRING",
    "default_value": "default",
    "targeting_key": "alice",
    "attributes": {
        "email": "alice@mycompany.com",
        "country": "US",
    },
    "expected_value": "green",
}


@pytest.fixture
def library_env(mock_ffe_agentless_backend: MockFFEAgentlessBackendServer) -> dict[str, str]:
    """Configure offline mode while leaving both network sources observable."""
    return {
        "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
        "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE": "offline",
        "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL": mock_ffe_agentless_backend.library_config_url,
        "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_POLL_INTERVAL_SECONDS": "0.2",
        "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_REQUEST_TIMEOUT_SECONDS": "1",
        "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
        "DD_API_KEY": TEST_API_KEY,
    }


def _evaluate(test_library: APMLibrary) -> dict[str, Any]:
    return evaluate_with_configuration_retry(
        test_library,
        flag=EVALUATION_CASE["flag"],
        variation_type=EVALUATION_CASE["variation_type"],
        default_value=EVALUATION_CASE["default_value"],
        targeting_key=EVALUATION_CASE["targeting_key"],
        attributes=EVALUATION_CASE["attributes"],
    )


def _assert_expected_value(result: dict[str, Any]) -> None:
    assert result.get("value") == EVALUATION_CASE["expected_value"]
    assert result.get("errorCode") in {None, ""}
    assert result.get("reason") != "ERROR"


def _assert_no_agentless_requests(mock_ffe_agentless_backend: MockFFEAgentlessBackendServer) -> None:
    for _ in range(OFFLINE_OBSERVATION_ATTEMPTS):
        status = mock_ffe_agentless_backend.status()
        assert status["requests_total"] == 0, f"offline mode made an agentless request: status={status}"
        time.sleep(OFFLINE_OBSERVATION_INTERVAL_SECONDS)


@scenarios.parametric
@features.feature_flags_offline
class Test_Feature_Flag_Offline_Evaluation:
    """Validate that offline delivery preserves the canonical UFC evaluation corpus."""

    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_offline_configuration_evaluates_fixture(
        self,
        test_case_file: str,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    ) -> None:
        assert test_library.ffe_start(offline_configuration=UFC_FIXTURE_BYTES), (
            "failed to start FFE provider with offline configuration"
        )

        assert_evaluation_cases(test_library, test_case_file)
        _assert_no_agentless_requests(mock_ffe_agentless_backend)


@scenarios.parametric
@features.feature_flags_offline
class Test_Feature_Flag_Offline_Startup:
    """Validate fail-closed startup and source isolation for offline mode."""

    @parametrize(
        "offline_configuration",
        [pytest.param(b"", id="empty"), pytest.param(MALFORMED_UFC_BYTES, id="malformed")],
    )
    def test_invalid_startup_configuration_fails_closed(
        self,
        offline_configuration: bytes,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    ) -> None:
        assert not test_library.ffe_start(offline_configuration=offline_configuration)
        _assert_no_agentless_requests(mock_ffe_agentless_backend)

    def test_offline_configuration_is_immutable_and_network_isolated(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    ) -> None:
        assert test_library.ffe_start(offline_configuration=UFC_FIXTURE_BYTES)
        _assert_expected_value(_evaluate(test_library))

        capabilities = test_agent.wait_for_rc_capabilities()
        assert Capabilities.FFE_FLAG_CONFIGURATION_RULES not in capabilities
        _assert_no_agentless_requests(mock_ffe_agentless_backend)

        _assert_expected_value(_evaluate(test_library))
