"""Parametric FFE configuration-source coverage for mocked FFE CDN validation.

Feature under test: server SDKs can select where UFC flag definitions come from.
The agentless path defaults to direct HTTP/CDN delivery, while explicit
``remote_config`` keeps the existing Agent RC path.

Test strategy: drive SDKs only through public env vars and OpenFeature evaluation
endpoints, then use the mock FFE CDN for observable HTTP behavior: request path,
auth, status transitions, ETag handling, retries, timeout, and poll overlap.
"""

from collections.abc import Callable
import json
from pathlib import Path
import time
from typing import Any

import pytest

from tests.parametric.conftest import APMLibrary
from tests.parametric.test_ffe.test_dynamic_evaluation import _set_and_wait_ffe_rc, _ffe_evaluate_with_rc_retry
from utils import features, scenarios
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures._mock_ffe_cdn import CONFIG_PATH, MockFFECDNServer, MockFFECDNStatus

parametrize = pytest.mark.parametrize
pytest_plugins = ["utils.docker_fixtures._mock_ffe_cdn"]

UFC_VALID_FIXTURE = Path(__file__).parent / "flags-v1.json"
RC_PRODUCT = "FFE_FLAGS"
TEST_API_KEY = "system-tests-mock-api-key"
MOCK_STATUS_ATTEMPTS = 25
MOCK_STATUS_INTERVAL_SECONDS = 0.2
NO_MOCK_REQUEST_ATTEMPTS = 5

BASE_ENVVARS = {
    "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.2",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
}

CDN_ENVVARS = {
    "DD_FLAGGING_CONFIGURATION_SOURCE_POLL_INTERVAL_SECONDS": "0.2",
    "DD_FLAGGING_CONFIGURATION_SOURCE_REQUEST_TIMEOUT_SECONDS": "1",
}

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


def _load_valid_ufc_fixture() -> dict[str, Any]:
    with UFC_VALID_FIXTURE.open() as f:
        return json.load(f)


UFC_VALID_DATA = _load_valid_ufc_fixture()


@pytest.fixture
def library_env(request: pytest.FixtureRequest, mock_ffe_cdn: MockFFECDNServer) -> dict[str, str]:
    params = getattr(request, "param", {})
    if not isinstance(params, dict):
        params = {}

    env = dict(BASE_ENVVARS)
    configuration_source = params.get("configuration_source", "cdn")
    response = params.get("response", "valid")
    responses = params.get("responses")
    api_key = params.get("api_key", TEST_API_KEY)

    if responses is not None:
        mock_ffe_cdn.set_responses(responses)
    elif response is not None:
        mock_ffe_cdn.set_response(str(response))

    if configuration_source is not None:
        env["DD_FLAGGING_CONFIGURATION_SOURCE"] = str(configuration_source)

    if params.get("cdn", True):
        base_url_form = params.get("base_url_form", "root")
        cdn_base_url = mock_ffe_cdn.library_config_url if base_url_form == "endpoint" else mock_ffe_cdn.library_base_url
        cdn_env = dict(CDN_ENVVARS)
        if "poll_interval" in params:
            cdn_env["DD_FLAGGING_CONFIGURATION_SOURCE_POLL_INTERVAL_SECONDS"] = str(params["poll_interval"])
        if "request_timeout" in params:
            cdn_env["DD_FLAGGING_CONFIGURATION_SOURCE_REQUEST_TIMEOUT_SECONDS"] = str(params["request_timeout"])
        env |= cdn_env
        env["DD_FLAGGING_CONFIGURATION_SOURCE_BASE_URL"] = cdn_base_url

    if api_key is not None:
        env["DD_API_KEY"] = str(api_key)

    return env


def _wait_for_status(
    mock_ffe_cdn: MockFFECDNServer, predicate: Callable[[MockFFECDNStatus], bool], description: str
) -> MockFFECDNStatus:
    last_status: MockFFECDNStatus | None = None
    for _ in range(MOCK_STATUS_ATTEMPTS):
        last_status = mock_ffe_cdn.status()
        if predicate(last_status):
            return last_status
        time.sleep(MOCK_STATUS_INTERVAL_SECONDS)

    pytest.fail(f"mock FFE CDN status did not reach expected state: {description}; status={last_status}", pytrace=False)
    raise AssertionError("unreachable")


def _assert_no_mock_requests(mock_ffe_cdn: MockFFECDNServer) -> None:
    status: MockFFECDNStatus | None = None
    for _ in range(NO_MOCK_REQUEST_ATTEMPTS):
        status = mock_ffe_cdn.status()
        assert status["requests_total"] == 0, f"unexpected mock FFE CDN request: status={status}"
        time.sleep(MOCK_STATUS_INTERVAL_SECONDS)


def _evaluate(test_library: APMLibrary) -> dict[str, Any]:
    return _ffe_evaluate_with_rc_retry(
        test_library,
        flag=EVALUATION_CASE["flag"],
        variation_type=EVALUATION_CASE["variation_type"],
        default_value=EVALUATION_CASE["default_value"],
        targeting_key=EVALUATION_CASE["targeting_key"],
        attributes=EVALUATION_CASE["attributes"],
    )


def _assert_expected_value(result: dict[str, Any]) -> None:
    assert result.get("value") == EVALUATION_CASE["expected_value"], "unexpected FFE evaluation value"
    assert result.get("errorCode") in {None, ""}
    assert result.get("reason") != "ERROR"


def _assert_default_or_not_ready(result: dict[str, Any]) -> None:
    assert result.get("value") == EVALUATION_CASE["default_value"]
    assert (
        result.get("errorCode")
        in {
            "PROVIDER_NOT_READY",
            "GENERAL",
            "PARSE_ERROR",
        }
        or result.get("reason") == "ERROR"
    )


def _has_status_sequence(status_codes: list[int], expected_status_codes: list[int]) -> bool:
    expected_length = len(expected_status_codes)
    return any(
        status_codes[index : index + expected_length] == expected_status_codes
        for index in range(len(status_codes) - expected_length + 1)
    )


@scenarios.parametric
@features.feature_flags_agentless
class Test_Feature_Flag_Configuration_Source_Selection:
    """Validate source selection for Agent RC, CDN, and customer endpoint overrides."""

    @parametrize("library_env", [{"configuration_source": "remote_config", "response": "valid"}], indirect=True)
    def test_remote_config_positive_ignores_cdn_env(
        self, test_agent: TestAgentAPI, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer
    ) -> None:
        mock_ffe_cdn.reset()
        apply_state = _set_and_wait_ffe_rc(test_agent, UFC_VALID_DATA)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert apply_state["product"] == RC_PRODUCT

        assert test_library.ffe_start(), "failed to start FFE provider in remote_config mode"
        _assert_expected_value(_evaluate(test_library))

        _assert_no_mock_requests(mock_ffe_cdn)

    @parametrize("library_env", [{"configuration_source": "remote_config", "response": "valid"}], indirect=True)
    def test_remote_config_without_rc_does_not_fallback_to_cdn(
        self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer
    ) -> None:
        mock_ffe_cdn.reset()

        assert test_library.ffe_start(), "failed to start FFE provider without remote_config payload"
        _assert_default_or_not_ready(_evaluate(test_library))

        _assert_no_mock_requests(mock_ffe_cdn)

    @parametrize(
        "library_env",
        [
            {"configuration_source": "cdn", "response": "valid", "base_url_form": "root"},
            {"configuration_source": "cdn", "response": "valid", "base_url_form": "endpoint"},
        ],
        indirect=True,
    )
    def test_explicit_cdn_positive(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider in explicit cdn mode"
        _assert_expected_value(_evaluate(test_library))

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["requests_total"] > 0 and current["last_status_code"] == 200,
            "valid response request",
        )
        assert status["last_auth_present"] is True
        assert status["last_path"] == CONFIG_PATH

    @parametrize("library_env", [{"configuration_source": None, "response": "valid"}], indirect=True)
    def test_default_cdn_positive(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider in default cdn mode"
        _assert_expected_value(_evaluate(test_library))

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["requests_total"] > 0 and current["last_status_code"] == 200,
            "default cdn request",
        )
        assert status["last_path"] == CONFIG_PATH

    @parametrize(
        "library_env",
        [{"configuration_source": None, "response": "valid", "base_url_form": "endpoint"}],
        indirect=True,
    )
    def test_customer_http_endpoint_default_cdn_positive(
        self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer
    ) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider with customer HTTP endpoint override"
        _assert_expected_value(_evaluate(test_library))

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["requests_total"] > 0 and current["last_status_code"] == 200,
            "customer HTTP endpoint request",
        )
        assert status["last_path"] == CONFIG_PATH

    @parametrize("library_env", [{"configuration_source": "invalid", "response": "valid"}], indirect=True)
    def test_invalid_configuration_source_fails_closed(
        self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer
    ) -> None:
        started = test_library.ffe_start()
        if started:
            _assert_default_or_not_ready(_evaluate(test_library))
        _assert_no_mock_requests(mock_ffe_cdn)


@scenarios.parametric
@features.feature_flags_agentless
class Test_Feature_Flag_Configuration_Source_Cold_Failure_And_Recovery:
    """Validate cold-start failure and recovery behavior for CDN configuration source."""

    @parametrize(
        "library_env",
        [{"configuration_source": "cdn", "response": "valid", "api_key": None}],
        indirect=True,
    )
    def test_missing_auth_cold(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for missing_auth_cold"
        _assert_default_or_not_ready(_evaluate(test_library))

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["last_status_code"] in {401, 403},
            "missing_auth_cold auth failure",
        )
        assert status["last_auth_present"] is False
        assert status["last_path"] == CONFIG_PATH

    @parametrize(
        "library_env",
        [{"configuration_source": "cdn", "response": "malformed"}],
        indirect=True,
    )
    def test_malformed_cold(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for malformed_cold"
        _assert_default_or_not_ready(_evaluate(test_library))

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["requests_total"] > 0 and current["last_status_code"] == 200,
            "malformed_cold response",
        )
        assert status["last_auth_present"] is True
        assert status["last_path"] == CONFIG_PATH

    @parametrize(
        "library_env",
        [{"configuration_source": "cdn", "response": "timeout", "poll_interval": "5", "request_timeout": "1"}],
        indirect=True,
    )
    def test_request_timeout_cold(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for request_timeout_cold"

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["requests_total"] > 0 and current["last_status_code"] == 200,
            "request_timeout_cold delayed valid response",
        )
        _assert_default_or_not_ready(_evaluate(test_library))
        assert status["last_auth_present"] is True
        assert status["last_path"] == CONFIG_PATH

    @parametrize(
        ("library_env", "expected_status_codes"),
        [
            pytest.param(
                {"configuration_source": "cdn", "responses": ["server_error", "valid"]},
                [500, 200],
                id="server-error-to-valid",
            ),
        ],
        indirect=["library_env"],
    )
    def test_bad_to_good_cold_recovery(
        self,
        test_library: APMLibrary,
        mock_ffe_cdn: MockFFECDNServer,
        expected_status_codes: list[int],
    ) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for bad_to_good"

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: _has_status_sequence(current["status_codes"], expected_status_codes),
            f"bad_to_good {expected_status_codes[0]} to 200 recovery",
        )
        _assert_expected_value(_evaluate(test_library))
        assert status["last_path"] == CONFIG_PATH

    @parametrize(
        ("library_env", "expected_status_codes"),
        [
            pytest.param(
                {"configuration_source": "cdn", "responses": ["server_error", "not_modified"]},
                [500, 304],
                id="server-error-to-unchanged",
            ),
        ],
        indirect=["library_env"],
    )
    def test_bad_to_unchanged_cold_preserves_not_ready(
        self,
        test_library: APMLibrary,
        mock_ffe_cdn: MockFFECDNServer,
        expected_status_codes: list[int],
    ) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for bad_to_unchanged"

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: _has_status_sequence(current["status_codes"], expected_status_codes),
            f"bad_to_unchanged {expected_status_codes[0]} to 304 cold sequence",
        )
        _assert_default_or_not_ready(_evaluate(test_library))
        assert status["last_path"] == CONFIG_PATH


@scenarios.parametric
@features.feature_flags_agentless
class Test_Feature_Flag_Configuration_Source_Warm_State_Preservation:
    """Validate that later CDN failures do not corrupt last-known-good state."""

    @parametrize("library_env", [{"configuration_source": "cdn", "response": "valid"}], indirect=True)
    def test_missing_auth_warm(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider before missing_auth_warm"
        _assert_expected_value(_evaluate(test_library))

        mock_ffe_cdn.set_response("unauthorized")
        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["last_status_code"] in {401, 403},
            "missing_auth_warm auth failure",
        )
        _assert_expected_value(_evaluate(test_library))
        assert status["requests_total"] > 0
        assert status["last_path"] == CONFIG_PATH

    @parametrize(
        ("library_env", "expected_status_codes"),
        [
            pytest.param(
                {"configuration_source": "cdn", "responses": ["valid", "server_error"]},
                [200, 500],
                id="valid-to-server-error",
            ),
        ],
        indirect=["library_env"],
    )
    def test_good_to_bad_warm_preservation(
        self,
        test_library: APMLibrary,
        mock_ffe_cdn: MockFFECDNServer,
        expected_status_codes: list[int],
    ) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for good_to_bad"

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: _has_status_sequence(current["status_codes"], expected_status_codes),
            f"good_to_bad 200 to {expected_status_codes[1]} preservation",
        )
        _assert_expected_value(_evaluate(test_library))
        assert status["last_path"] == CONFIG_PATH

    @parametrize(
        "library_env", [{"configuration_source": "cdn", "responses": ["valid", "not_modified"]}], indirect=True
    )
    def test_good_to_unchanged_etag_sequence(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for good_to_unchanged"

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: _has_status_sequence(current["status_codes"], [200, 304])
            and current["last_if_none_match"] == '"ufc-v1"',
            "good_to_unchanged 200 to 304 ETag sequence",
        )
        _assert_expected_value(_evaluate(test_library))
        assert status["last_path"] == CONFIG_PATH

    @parametrize("library_env", [{"configuration_source": "cdn", "response": "valid"}], indirect=True)
    def test_malformed_warm(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider before malformed_warm"
        _assert_expected_value(_evaluate(test_library))

        requests_before = mock_ffe_cdn.status()["requests_total"]
        mock_ffe_cdn.set_response("malformed")
        _wait_for_status(
            mock_ffe_cdn,
            lambda current: (current["requests_total"] > requests_before and current["last_status_code"] == 200),
            "malformed_warm response",
        )
        _assert_expected_value(_evaluate(test_library))
        assert mock_ffe_cdn.status()["last_path"] == CONFIG_PATH


@scenarios.parametric
@features.feature_flags_agentless
class Test_Feature_Flag_Configuration_Source_Poller_Concurrency:
    """Validate that CDN polling does not overlap requests under slow responses."""

    @parametrize("library_env", [{"configuration_source": "cdn", "response": "delayed_valid"}], indirect=True)
    def test_delayed_no_overlap(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for delayed_no_overlap"
        _assert_expected_value(_evaluate(test_library))

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: (
                current["requests_total"] > 0
                and current["last_status_code"] == 200
                and current["in_flight"] == 0
                and current["max_in_flight"] >= 1
            ),
            "delayed_no_overlap completion",
        )
        assert status["max_in_flight"] == 1
        assert status["last_path"] == CONFIG_PATH


@scenarios.parametric
@features.feature_flags_agentless
class Test_Feature_Flag_Configuration_Source_Mock_Fixture:
    """Validate that the mock CDN exposes only metadata needed by the tests."""

    def test_mock_ffe_cdn_status_is_metadata_only(self, mock_ffe_cdn: MockFFECDNServer) -> None:
        status = mock_ffe_cdn.status()
        assert set(status) == {
            "requests_total",
            "in_flight",
            "max_in_flight",
            "last_path",
            "last_if_none_match",
            "last_auth_present",
            "last_status_code",
            "status_codes",
        }
        assert "ufc" not in status
        assert "payload" not in status
        assert "body" not in status
