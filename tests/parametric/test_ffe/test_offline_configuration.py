"""Parametric contract for startup-only offline UFC configuration.

Offline mode receives UFC JSON bytes through the provider API. It must preserve
the same evaluation semantics as Agent RC and agentless delivery while making
no configuration request and accepting no runtime update.
"""

import base64
import copy
import time
from typing import Any

import pytest

from tests.parametric.conftest import APMLibrary
from tests.parametric.test_ffe.utils import (
    ALL_TEST_CASE_FILES,
    UFC_FIXTURE_DATA,
    UFC_FIXTURE_BYTES,
    assert_evaluation_cases,
)
from utils import features, scenarios
from utils.dd_constants import Capabilities
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures._mock_ffe_agentless_backend import (
    MALFORMED_UFC_BYTES,
    MockFFEAgentlessBackendServer,
)

parametrize = pytest.mark.parametrize
pytest_plugins = ["utils.docker_fixtures._mock_ffe_agentless_backend"]

OFFLINE_OBSERVATION_INTERVAL_SECONDS = 0.2
OFFLINE_OBSERVATION_ATTEMPTS = 5
TEST_API_KEY = "system-tests-mock-api-key"
RC_PRODUCT = "FFE_FLAGS"
RC_REPLACEMENT_PATH = f"datadog/2/{RC_PRODUCT}/offline-replacement/config"

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


def _replacement_ufc_data() -> dict[str, Any]:
    configuration = copy.deepcopy(UFC_FIXTURE_DATA)
    configuration["flags"]["new-user-onboarding"]["variations"]["green"]["value"] = "replacement"
    return configuration


REPLACEMENT_UFC_DATA = _replacement_ufc_data()


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
    return test_library.ffe_evaluate(
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


def _rc_capabilities_bitmask(raw_capabilities: object) -> int:
    if raw_capabilities in (None, "", []):
        return 0
    if isinstance(raw_capabilities, list):
        return int.from_bytes(bytes(raw_capabilities), byteorder="big")
    if isinstance(raw_capabilities, str):
        return int.from_bytes(base64.b64decode(raw_capabilities), byteorder="big")
    raise AssertionError(f"unexpected Remote Configuration capabilities value: {raw_capabilities!r}")


def _assert_no_agentless_requests(mock_ffe_agentless_backend: MockFFEAgentlessBackendServer) -> None:
    status = mock_ffe_agentless_backend.status()
    assert status["requests_total"] == 0, f"offline mode made an agentless request: status={status}"


def _assert_configuration_sources_remain_offline(
    test_agent: TestAgentAPI,
    mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
) -> None:
    """Observe that neither network source becomes active for offline Feature Flagging."""
    for attempt in range(OFFLINE_OBSERVATION_ATTEMPTS):
        _assert_no_agentless_requests(mock_ffe_agentless_backend)
        for request in test_agent.rc_requests():
            client = request.get("body", {}).get("client", {})
            products = client.get("products", [])
            assert RC_PRODUCT not in products, f"offline mode subscribed to {RC_PRODUCT}: request={request}"

            capabilities = _rc_capabilities_bitmask(client.get("capabilities"))
            ffe_capability = 1 << Capabilities.FFE_FLAG_CONFIGURATION_RULES
            assert (capabilities & ffe_capability) == 0, (
                f"offline mode advertised the FFE Remote Configuration capability: request={request}"
            )

        if attempt < OFFLINE_OBSERVATION_ATTEMPTS - 1:
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

        assert_evaluation_cases(test_library, test_case_file, allow_configuration_retry=False)
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
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    ) -> None:
        assert not test_library.ffe_start(offline_configuration=offline_configuration)
        _assert_configuration_sources_remain_offline(test_agent, mock_ffe_agentless_backend)

    def test_offline_configuration_is_immutable_and_network_isolated(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    ) -> None:
        assert test_library.ffe_start(offline_configuration=UFC_FIXTURE_BYTES)
        _assert_expected_value(_evaluate(test_library))

        test_agent.set_remote_config(path=RC_REPLACEMENT_PATH, payload=REPLACEMENT_UFC_DATA)
        _assert_configuration_sources_remain_offline(test_agent, mock_ffe_agentless_backend)

        _assert_expected_value(_evaluate(test_library))
