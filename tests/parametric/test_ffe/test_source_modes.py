"""Parametric FFE source-mode coverage for mocked FFE CDN validation."""

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
from utils.docker_fixtures._mock_ffe_cdn import MockFFECDNServer, MockFFECDNStatus

parametrize = pytest.mark.parametrize
pytest_plugins = ["utils.docker_fixtures._mock_ffe_cdn"]

UFC_VALID_FIXTURE = Path(__file__).parent / "flags-v1.json"
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
def library_env(request: pytest.FixtureRequest, mock_ffe_cdn: MockFFECDNServer) -> dict[str, str]:
    params = getattr(request, "param", {})
    if not isinstance(params, dict):
        params = {}

    env = dict(BASE_ENVVARS)
    source_mode = params.get("source_mode", "cdn")
    fixture = params.get("fixture", "valid_control")
    api_key = params.get("api_key", TEST_API_KEY)

    if fixture is not None:
        mock_ffe_cdn.set_fixture(str(fixture))

    if source_mode is not None:
        env["DD_FLAGGING_SOURCE_MODE"] = str(source_mode)

    if params.get("cdn", True):
        base_url_form = params.get("base_url_form", "root")
        cdn_base_url = mock_ffe_cdn.library_config_url if base_url_form == "endpoint" else mock_ffe_cdn.library_base_url
        env |= CDN_ENVVARS
        env["DD_FLAGGING_CDN_BASE_URL"] = cdn_base_url

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


@scenarios.parametric
@features.feature_flags_dynamic_evaluation
class Test_Feature_Flag_Source_Modes:
    """Validate Feature Flag source modes against RC and a mocked FFE CDN."""

    @parametrize("library_env", [{"source_mode": "remote_config", "cdn": False}], indirect=True)
    def test_remote_config_positive_suppresses_cdn(
        self, test_agent: TestAgentAPI, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer
    ) -> None:
        mock_ffe_cdn.reset()
        apply_state = _set_and_wait_ffe_rc(test_agent, UFC_VALID_DATA)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert apply_state["product"] == RC_PRODUCT

        assert test_library.ffe_start(UFC_VALID_DATA), "failed to start FFE provider in remote_config mode"
        _assert_expected_value(_evaluate(test_library))

        status = mock_ffe_cdn.status()
        assert status["requests_total"] == 0

    @parametrize(
        "library_env",
        [
            {"source_mode": "cdn", "fixture": "valid_control", "base_url_form": "root"},
            {"source_mode": "cdn", "fixture": "valid_control", "base_url_form": "endpoint"},
        ],
        indirect=True,
    )
    def test_explicit_cdn_positive(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider in explicit cdn mode"
        _assert_expected_value(_evaluate(test_library))

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["requests_total"] > 0 and current["last_status_code"] == 200,
            "valid_control request",
        )
        assert status["fixture"] == "valid_control"
        assert status["last_auth_present"] is True
        assert status["last_source_mode"] == "cdn"

    @parametrize("library_env", [{"source_mode": None, "fixture": "valid_control"}], indirect=True)
    def test_default_cdn_positive(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider in default cdn mode"
        _assert_expected_value(_evaluate(test_library))

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["requests_total"] > 0 and current["last_status_code"] == 200,
            "default cdn request",
        )
        assert status["fixture"] == "valid_control"
        assert status["last_source_mode"] == "cdn"

    @parametrize(
        "library_env",
        [{"source_mode": None, "fixture": "valid_control", "base_url_form": "endpoint"}],
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
        assert status["fixture"] == "valid_control"
        assert status["last_path"] == "/mock/ufc/config"
        assert status["last_source_mode"] == "cdn"

    @parametrize(
        "library_env",
        [{"source_mode": "cdn", "fixture": "missing_auth_cold", "api_key": None}],
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
        assert status["fixture"] == "missing_auth_cold"
        assert status["last_auth_present"] is False
        assert status["last_source_mode"] == "cdn"

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "valid_control"}], indirect=True)
    def test_missing_auth_warm(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider before missing_auth_warm"
        _assert_expected_value(_evaluate(test_library))

        mock_ffe_cdn.set_fixture("missing_auth_warm")
        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["fixture"] == "missing_auth_warm" and current["last_status_code"] in {401, 403},
            "missing_auth_warm auth failure",
        )
        _assert_expected_value(_evaluate(test_library))
        assert status["requests_total"] > 0
        assert status["last_source_mode"] == "cdn"

    @parametrize(
        "library_env",
        [{"source_mode": "cdn", "fixture": "malformed_cold"}],
        indirect=True,
    )
    def test_malformed_cold(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for malformed_cold"
        _assert_default_or_not_ready(_evaluate(test_library))

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["fixture"] == "malformed_cold" and current["last_status_code"] == 200,
            "malformed_cold response",
        )
        assert status["last_auth_present"] is True
        assert status["last_source_mode"] == "cdn"

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "valid_control"}], indirect=True)
    def test_malformed_warm(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider before malformed_warm"
        _assert_expected_value(_evaluate(test_library))

        requests_before = mock_ffe_cdn.status()["requests_total"]
        mock_ffe_cdn.set_fixture("malformed_warm")
        _wait_for_status(
            mock_ffe_cdn,
            lambda current: (
                current["fixture"] == "malformed_warm"
                and current["requests_total"] > requests_before
                and current["last_status_code"] == 200
            ),
            "malformed_warm response",
        )
        _assert_expected_value(_evaluate(test_library))
        assert mock_ffe_cdn.status()["last_source_mode"] == "cdn"

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "valid_control"}], indirect=True)
    def test_unchanged_etag_304(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider before unchanged_etag_304"
        _assert_expected_value(_evaluate(test_library))

        mock_ffe_cdn.set_fixture("unchanged_etag_304")
        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: (
                current["fixture"] == "unchanged_etag_304"
                and current["last_status_code"] == 304
                and current["last_if_none_match"] is not None
            ),
            "unchanged_etag_304 conditional request",
        )
        _assert_expected_value(_evaluate(test_library))
        assert status["last_if_none_match"] == '"ufc-v1"'
        assert status["last_source_mode"] == "cdn"

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "explicit_source_mode"}], indirect=True)
    def test_explicit_source_mode(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for explicit_source_mode"
        _assert_expected_value(_evaluate(test_library))

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["fixture"] == "explicit_source_mode" and current["requests_total"] > 0,
            "explicit_source_mode request",
        )
        assert status["last_source_mode"] == "cdn"

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "bad_to_good"}], indirect=True)
    def test_bad_to_good_cold_recovery(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for bad_to_good"

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["status_codes"][-2:] == [509, 200],
            "bad_to_good 509 to 200 recovery",
        )
        _assert_expected_value(_evaluate(test_library))
        assert status["last_source_mode"] == "cdn"

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "error_500_to_good"}], indirect=True)
    def test_500_to_good_cold_recovery(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for error_500_to_good"

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["status_codes"][-2:] == [500, 200],
            "error_500_to_good 500 to 200 recovery",
        )
        _assert_expected_value(_evaluate(test_library))
        assert status["last_source_mode"] == "cdn"

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "bad_to_unchanged"}], indirect=True)
    def test_bad_to_unchanged_cold_preserves_not_ready(
        self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer
    ) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for bad_to_unchanged"

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["status_codes"][-2:] == [509, 304],
            "bad_to_unchanged 509 to 304 cold sequence",
        )
        _assert_default_or_not_ready(_evaluate(test_library))
        assert status["last_source_mode"] == "cdn"

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "good_to_bad"}], indirect=True)
    def test_good_to_bad_warm_preservation(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for good_to_bad"

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["status_codes"][-2:] == [200, 509],
            "good_to_bad 200 to 509 preservation",
        )
        _assert_expected_value(_evaluate(test_library))
        assert status["last_source_mode"] == "cdn"

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "good_to_unchanged"}], indirect=True)
    def test_good_to_unchanged_etag_sequence(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for good_to_unchanged"

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: current["status_codes"][-2:] == [200, 304] and current["last_if_none_match"] == '"ufc-v1"',
            "good_to_unchanged 200 to 304 ETag sequence",
        )
        _assert_expected_value(_evaluate(test_library))
        assert status["last_source_mode"] == "cdn"

    @parametrize("library_env", [{"source_mode": "cdn", "fixture": "delayed_no_overlap"}], indirect=True)
    def test_delayed_no_overlap(self, test_library: APMLibrary, mock_ffe_cdn: MockFFECDNServer) -> None:
        assert test_library.ffe_start(), "failed to start FFE provider for delayed_no_overlap"
        _assert_expected_value(_evaluate(test_library))

        status = _wait_for_status(
            mock_ffe_cdn,
            lambda current: (
                current["fixture"] == "delayed_no_overlap"
                and current["in_flight"] == 0
                and current["max_in_flight"] >= 1
            ),
            "delayed_no_overlap completion",
        )
        assert status["max_in_flight"] == 1
        assert status["last_source_mode"] == "cdn"

    def test_mock_ffe_cdn_status_is_metadata_only(self, mock_ffe_cdn: MockFFECDNServer) -> None:
        status = mock_ffe_cdn.status()
        assert set(status) == {
            "fixture",
            "requests_total",
            "in_flight",
            "max_in_flight",
            "last_path",
            "last_query",
            "last_if_none_match",
            "last_auth_present",
            "last_source_mode",
            "last_status_code",
            "status_codes",
        }
        assert "ufc" not in status
        assert "payload" not in status
        assert "body" not in status
