"""Parametric FFE source-mode coverage for mocked CDN validation."""

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
from utils.docker_fixtures._mock_cdn import MockCDNServer, mock_cdn

parametrize = pytest.mark.parametrize

FIXTURE_DIR = Path(__file__).parent / "fixtures"
UFC_VALID_FIXTURE = FIXTURE_DIR / "ufc_valid.json"
RC_PRODUCT = "FFE_FLAGS"
TEST_API_KEY = "system-tests-mock-api-key"
MOCK_STATUS_ATTEMPTS = 25
MOCK_STATUS_INTERVAL_SECONDS = 0.2

BASE_ENVVARS = {
    "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.2",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
}

CDN_ENVVARS = {
    "DD_FLAGGING_CDN_POLL_INTERVAL_SECONDS": "0.2",
    "DD_FLAGGING_CDN_REQUEST_TIMEOUT_SECONDS": "1",
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
def library_env(request: pytest.FixtureRequest, mock_cdn: MockCDNServer) -> dict[str, str]:
    params = getattr(request, "param", {})
    if not isinstance(params, dict):
        params = {}

    env = dict(BASE_ENVVARS)
    source_mode = params.get("source_mode", "cdn")
    fixture = params.get("fixture", "valid_control")
    api_key = params.get("api_key", TEST_API_KEY)

    if fixture is not None:
        mock_cdn.set_fixture(str(fixture))

    if source_mode is not None:
        env["DD_FLAGGING_SOURCE_MODE"] = str(source_mode)

    if params.get("cdn", True):
        env |= CDN_ENVVARS
        env["DD_FLAGGING_CDN_BASE_URL"] = mock_cdn.library_base_url

    if api_key is not None:
        env["DD_API_KEY"] = str(api_key)

    return env


def _wait_for_status(
    mock_cdn: MockCDNServer, predicate: Callable[[dict[str, Any]], bool], description: str
) -> dict[str, Any]:
    last_status: dict[str, Any] = {}
    for _ in range(MOCK_STATUS_ATTEMPTS):
        last_status = mock_cdn.status()
        if predicate(last_status):
            return last_status
        time.sleep(MOCK_STATUS_INTERVAL_SECONDS)

    pytest.fail(f"mock CDN status did not reach expected state: {description}; status={last_status}", pytrace=False)


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


def _assert_default_or_not_ready(result: dict[str, Any]) -> None:
    assert result.get("value") == EVALUATION_CASE["default_value"] or result.get("errorCode") in {
        "PROVIDER_NOT_READY",
        "GENERAL",
        "PARSE_ERROR",
    }


@scenarios.parametric
@features.feature_flags_dynamic_evaluation
class Test_Feature_Flag_Source_Modes:
    """Validate Feature Flag source modes against RC and a mocked CDN."""

    @parametrize("library_env", [{"source_mode": "remote_config", "cdn": False}], indirect=True)
    def test_remote_config_positive_suppresses_cdn(
        self, test_agent: TestAgentAPI, test_library: APMLibrary, mock_cdn: MockCDNServer
    ) -> None:
        mock_cdn.reset()
        apply_state = _set_and_wait_ffe_rc(test_agent, UFC_VALID_DATA)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert apply_state["product"] == RC_PRODUCT

        assert test_library.ffe_start(UFC_VALID_DATA), "failed to start FFE provider in remote_config mode"
        _assert_expected_value(_evaluate(test_library))

        status = mock_cdn.status()
        assert status["requests_total"] == 0

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "valid_control"}], indirect=True)
    def test_explicit_cdn_positive(self, test_library: APMLibrary, mock_cdn: MockCDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider in explicit cdn mode"
        _assert_expected_value(_evaluate(test_library))

        status = _wait_for_status(
            mock_cdn,
            lambda current: current["requests_total"] > 0 and current["last_status_code"] == 200,
            "valid_control request",
        )
        assert status["fixture"] == "valid_control"
        assert status["last_auth_present"] is True

    @parametrize("library_env", [{"source_mode": None, "fixture": "valid_control"}], indirect=True)
    def test_default_cdn_positive(self, test_library: APMLibrary, mock_cdn: MockCDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider in default cdn mode"
        _assert_expected_value(_evaluate(test_library))

        status = _wait_for_status(
            mock_cdn,
            lambda current: current["requests_total"] > 0 and current["last_status_code"] == 200,
            "default cdn request",
        )
        assert status["fixture"] == "valid_control"

    @parametrize(
        "library_env",
        [{"source_mode": "cdn", "fixture": "missing_auth_cold", "api_key": None}],
        indirect=True,
    )
    def test_missing_auth_cold(self, test_library: APMLibrary, mock_cdn: MockCDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for missing_auth_cold"
        _assert_default_or_not_ready(_evaluate(test_library))

        status = _wait_for_status(
            mock_cdn,
            lambda current: current["last_status_code"] in {401, 403},
            "missing_auth_cold auth failure",
        )
        assert status["fixture"] == "missing_auth_cold"
        assert status["last_auth_present"] is False

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "valid_control"}], indirect=True)
    def test_missing_auth_warm(self, test_library: APMLibrary, mock_cdn: MockCDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider before missing_auth_warm"
        _assert_expected_value(_evaluate(test_library))

        mock_cdn.set_fixture("missing_auth_warm")
        status = _wait_for_status(
            mock_cdn,
            lambda current: current["fixture"] == "missing_auth_warm" and current["last_status_code"] in {401, 403},
            "missing_auth_warm auth failure",
        )
        _assert_expected_value(_evaluate(test_library))
        assert status["requests_total"] > 0

    @parametrize(
        "library_env",
        [{"source_mode": "cdn", "fixture": "malformed_cold"}],
        indirect=True,
    )
    def test_malformed_cold(self, test_library: APMLibrary, mock_cdn: MockCDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for malformed_cold"
        _assert_default_or_not_ready(_evaluate(test_library))

        status = _wait_for_status(
            mock_cdn,
            lambda current: current["fixture"] == "malformed_cold" and current["last_status_code"] == 200,
            "malformed_cold response",
        )
        assert status["last_auth_present"] is True

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "valid_control"}], indirect=True)
    def test_malformed_warm(self, test_library: APMLibrary, mock_cdn: MockCDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider before malformed_warm"
        _assert_expected_value(_evaluate(test_library))

        mock_cdn.set_fixture("malformed_warm")
        _wait_for_status(
            mock_cdn,
            lambda current: current["fixture"] == "malformed_warm" and current["last_status_code"] == 200,
            "malformed_warm response",
        )
        _assert_expected_value(_evaluate(test_library))

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "valid_control"}], indirect=True)
    def test_unchanged_etag_304(self, test_library: APMLibrary, mock_cdn: MockCDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider before unchanged_etag_304"
        _assert_expected_value(_evaluate(test_library))

        mock_cdn.set_fixture("unchanged_etag_304")
        status = _wait_for_status(
            mock_cdn,
            lambda current: current["fixture"] == "unchanged_etag_304"
            and current["last_status_code"] == 304
            and current["last_if_none_match"] is not None,
            "unchanged_etag_304 conditional request",
        )
        _assert_expected_value(_evaluate(test_library))
        assert status["last_if_none_match"] == '"ufc-v1"'

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "explicit_source_mode"}], indirect=True)
    def test_explicit_source_mode(self, test_library: APMLibrary, mock_cdn: MockCDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for explicit_source_mode"
        _assert_expected_value(_evaluate(test_library))

        status = _wait_for_status(
            mock_cdn,
            lambda current: current["fixture"] == "explicit_source_mode" and current["requests_total"] > 0,
            "explicit_source_mode request",
        )
        assert status["last_source_mode"] == "cdn"

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "delayed_no_overlap"}], indirect=True)
    def test_delayed_no_overlap(self, test_library: APMLibrary, mock_cdn: MockCDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for delayed_no_overlap"
        _assert_expected_value(_evaluate(test_library))

        status = _wait_for_status(
            mock_cdn,
            lambda current: current["fixture"] == "delayed_no_overlap"
            and current["in_flight"] == 0
            and current["max_in_flight"] >= 1,
            "delayed_no_overlap completion",
        )
        assert status["max_in_flight"] == 1
