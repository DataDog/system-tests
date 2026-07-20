"""Parametric FFE configuration-source coverage for a mocked FFE agentless backend.

Feature under test: server SDKs preserve legacy Remote Configuration adopters,
load UFC flag definitions from the agentless HTTP backend by default only after
application provider access, and honor explicit source selection and the stable
provider kill switch.

Test strategy: drive SDKs through public configuration-source env vars and
OpenFeature evaluation endpoints, then use the mock FFE agentless backend for
observable HTTP behavior: request path, auth, status transitions, ETag handling,
retries, timeout, and poll overlap. The mock endpoint is passed through the
agentless base URL option; it does not introduce a separate custom source mode.
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
from utils.dd_constants import Capabilities, RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures._mock_ffe_agentless_backend import (
    CONFIG_PATH,
    MockFFEAgentlessBackendServer,
    MockFFEAgentlessBackendStatus,
)

parametrize = pytest.mark.parametrize
pytest_plugins = ["utils.docker_fixtures._mock_ffe_agentless_backend"]

UFC_VALID_FIXTURE = Path(__file__).parent / "flags-v1.json"
RC_PRODUCT = "FFE_FLAGS"
TEST_API_KEY = "system-tests-mock-api-key"
MOCK_STATUS_ATTEMPTS = 25
MOCK_STATUS_INTERVAL_SECONDS = 0.2
NO_MOCK_REQUEST_ATTEMPTS = 5
AGENTLESS_BASE_URL = "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL"

BASE_ENVVARS = {
    "DD_INSTRUMENTATION_TELEMETRY_ENABLED": "false",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
}

AGENTLESS_ENVVARS = {
    "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_POLL_INTERVAL_SECONDS": "1",
    "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_REQUEST_TIMEOUT_SECONDS": "1",
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
def library_env(
    request: pytest.FixtureRequest, mock_ffe_agentless_backend: MockFFEAgentlessBackendServer
) -> dict[str, str]:
    params = getattr(request, "param", {})
    if not isinstance(params, dict):
        params = {}

    env = dict(BASE_ENVVARS)
    configuration_source = params.get("configuration_source", "agentless")
    response = params.get("response", "valid")
    responses = params.get("responses")
    api_key = params.get("api_key", TEST_API_KEY)

    if "provider_enabled" in params:
        env["DD_FEATURE_FLAGS_ENABLED"] = str(params["provider_enabled"]).lower()
    if "legacy_provider_enabled" in params:
        env["DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED"] = str(params["legacy_provider_enabled"]).lower()

    if responses is not None:
        mock_ffe_agentless_backend.set_responses(responses)
    elif response is not None:
        mock_ffe_agentless_backend.set_response(str(response))

    if configuration_source is not None:
        env["DD_FEATURE_FLAGS_CONFIGURATION_SOURCE"] = str(configuration_source)

    if params.get("agentless", True):
        agentless_env = dict(AGENTLESS_ENVVARS)
        if "poll_interval" in params:
            agentless_env["DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_POLL_INTERVAL_SECONDS"] = str(
                params["poll_interval"]
            )
        if "request_timeout" in params:
            agentless_env["DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_REQUEST_TIMEOUT_SECONDS"] = str(
                params["request_timeout"]
            )
        env |= agentless_env
        env[AGENTLESS_BASE_URL] = mock_ffe_agentless_backend.library_config_url

    if api_key is not None:
        env["DD_API_KEY"] = str(api_key)

    return env


def _wait_for_status(
    mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    predicate: Callable[[MockFFEAgentlessBackendStatus], bool],
    description: str,
) -> MockFFEAgentlessBackendStatus:
    last_status: MockFFEAgentlessBackendStatus | None = None
    for _ in range(MOCK_STATUS_ATTEMPTS):
        last_status = mock_ffe_agentless_backend.status()
        if predicate(last_status):
            return last_status
        time.sleep(MOCK_STATUS_INTERVAL_SECONDS)

    pytest.fail(
        f"mock FFE agentless backend status did not reach expected state: {description}; status={last_status}",
        pytrace=False,
    )
    raise AssertionError("unreachable")


def _assert_no_mock_requests(mock_ffe_agentless_backend: MockFFEAgentlessBackendServer) -> None:
    status: MockFFEAgentlessBackendStatus | None = None
    for _ in range(NO_MOCK_REQUEST_ATTEMPTS):
        status = mock_ffe_agentless_backend.status()
        assert status["requests_total"] == 0, f"unexpected mock FFE agentless backend request: status={status}"
        time.sleep(MOCK_STATUS_INTERVAL_SECONDS)


def _remote_config_products(test_agent: TestAgentAPI) -> set[str]:
    products: set[str] = set()
    for request in test_agent.rc_requests(post_only=True):
        client = request["body"].get("client", {})
        products.update(client.get("products", []))
    return products


def _assert_ffe_remote_config_activation(test_agent: TestAgentAPI) -> None:
    test_agent.assert_rc_capabilities({Capabilities.FFE_FLAG_CONFIGURATION_RULES})
    assert RC_PRODUCT in _remote_config_products(test_agent)


def _assert_no_ffe_remote_config_activation(test_agent: TestAgentAPI) -> None:
    for _ in range(NO_MOCK_REQUEST_ATTEMPTS):
        capabilities = test_agent.wait_for_rc_capabilities()
        assert Capabilities.FFE_FLAG_CONFIGURATION_RULES not in capabilities
        assert RC_PRODUCT not in _remote_config_products(test_agent)
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


def _assert_cold_not_ready(test_library: APMLibrary, *, started: bool) -> None:
    if started:
        _assert_default_or_not_ready(_evaluate(test_library))


def _has_status_sequence(status_codes: list[int], expected_status_codes: list[int]) -> bool:
    expected_length = len(expected_status_codes)
    return any(
        status_codes[index : index + expected_length] == expected_status_codes
        for index in range(len(status_codes) - expected_length + 1)
    )


@scenarios.parametric
@features.feature_flags_agentless
class Test_Feature_Flag_Configuration_Source_Selection:
    """Validate source selection for Agent RC and agentless endpoint choices."""

    @parametrize("library_env", [{"configuration_source": "remote_config", "response": "valid"}], indirect=True)
    def test_remote_config_positive_ignores_agentless_env(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    ) -> None:
        # Explicit remote_config is combined with the agentless URL and poller inputs that
        # library_env supplies by default, distinguishing source selection from CDN availability.
        # The RC ACK, product/capability, and evaluation prove RC supplied the UFC data; zero mock
        # requests proves the configured agentless endpoint was not used.
        apply_state = _set_and_wait_ffe_rc(test_agent, UFC_VALID_DATA)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert apply_state["product"] == RC_PRODUCT
        _assert_ffe_remote_config_activation(test_agent)

        assert test_library.ffe_start(), "failed to start FFE provider in remote_config mode"
        _assert_expected_value(_evaluate(test_library))

        _assert_no_mock_requests(mock_ffe_agentless_backend)

    @parametrize(
        "library_env",
        [{"configuration_source": "remote_config", "provider_enabled": False, "response": "valid"}],
        indirect=True,
    )
    def test_provider_kill_switch_stops_remote_config_subscription(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    ) -> None:
        # remote_config requests the eager RC path, while DD_FEATURE_FLAGS_ENABLED=false supplies
        # the conflicting global kill-switch input and a valid agentless backend remains available.
        # Absence of the FFE RC capability/product and zero mock requests after provider access
        # prove the kill switch prevents both billed delivery paths.
        test_library.ffe_start()
        _assert_no_ffe_remote_config_activation(test_agent)
        _assert_no_mock_requests(mock_ffe_agentless_backend)

    @parametrize("library_env", [{"configuration_source": "remote_config", "response": "valid"}], indirect=True)
    def test_remote_config_without_rc_does_not_fallback_to_agentless(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    ) -> None:
        # Explicit remote_config is tested with usable agentless inputs but without delivering an
        # RC payload, making a tempting fallback destination available when RC has no configuration.
        # The advertised FFE RC capability proves RC stayed selected, while zero mock requests
        # proves payload absence never changes the configured source to agentless.
        del test_library  # fixture starts the tracer; no RC payload is delivered

        _assert_ffe_remote_config_activation(test_agent)
        _assert_no_mock_requests(mock_ffe_agentless_backend)

    @parametrize("library_env", [{"configuration_source": None, "response": "valid"}], indirect=True)
    def test_default_agentless_positive(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    ) -> None:
        # Omitting the source and both legacy/stable enablement variables models a new customer;
        # the base URL, API key, and polling inputs make the controlled agentless backend usable.
        # Zero startup traffic proves default agentless is lazy; the post-access value, authenticated
        # CONFIG_PATH request, and absent RC capability prove provider access activates only CDN.
        _assert_no_mock_requests(mock_ffe_agentless_backend)
        _assert_no_ffe_remote_config_activation(test_agent)

        assert test_library.ffe_start(), "failed to start FFE provider in default agentless mode"
        _assert_expected_value(_evaluate(test_library))

        status = _wait_for_status(
            mock_ffe_agentless_backend,
            lambda current: current["requests_total"] > 0 and current["last_status_code"] == 200,
            "valid response request",
        )
        assert status["last_auth_present"] is True
        assert status["last_path"] == CONFIG_PATH
        _assert_no_ffe_remote_config_activation(test_agent)

    @parametrize(
        "library_env",
        [{"configuration_source": None, "legacy_provider_enabled": True, "response": "valid"}],
        indirect=True,
    )
    def test_legacy_true_preserves_remote_config(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    ) -> None:
        # With no explicit source, DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED=true represents an
        # existing customer whose historical opt-in selected Remote Configuration; the valid CDN
        # inputs ensure agentless would otherwise be available. RC ACK/capability and the expected
        # evaluation prove grandfathering, while zero mock requests proves there was no migration.
        apply_state = _set_and_wait_ffe_rc(test_agent, UFC_VALID_DATA)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert apply_state["product"] == RC_PRODUCT
        _assert_ffe_remote_config_activation(test_agent)

        assert test_library.ffe_start(), "failed to start grandfathered Remote Config provider"
        _assert_expected_value(_evaluate(test_library))
        _assert_no_mock_requests(mock_ffe_agentless_backend)

    @parametrize(
        "library_env",
        [{"configuration_source": None, "legacy_provider_enabled": False, "response": "valid"}],
        indirect=True,
    )
    def test_legacy_false_keeps_provider_disabled(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    ) -> None:
        # With no explicit source, DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED=false models a customer
        # who explicitly disabled the legacy provider even though a valid CDN endpoint is configured.
        # Zero agentless requests and no FFE RC capability/product after provider access prove the
        # legacy false value remains disabled instead of adopting the new default.
        test_library.ffe_start()
        _assert_no_mock_requests(mock_ffe_agentless_backend)
        _assert_no_ffe_remote_config_activation(test_agent)

    @parametrize(
        "library_env",
        [{"configuration_source": "agentless", "legacy_provider_enabled": True, "response": "valid"}],
        indirect=True,
    )
    def test_explicit_agentless_wins_over_legacy_true(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    ) -> None:
        # DD_FEATURE_FLAGS_CONFIGURATION_SOURCE=agentless conflicts intentionally with legacy true,
        # proving that the stable explicit source can migrate a grandfathered RC customer to CDN.
        # Startup silence proves lazy activation; the expected value and backend request after access,
        # together with the absent RC capability, prove agentless wins exclusively.
        _assert_no_mock_requests(mock_ffe_agentless_backend)
        _assert_no_ffe_remote_config_activation(test_agent)

        assert test_library.ffe_start(), "failed to start explicit agentless provider"
        _assert_expected_value(_evaluate(test_library))
        _wait_for_status(
            mock_ffe_agentless_backend,
            lambda current: current["requests_total"] > 0 and current["last_status_code"] == 200,
            "explicit agentless response request",
        )
        _assert_no_ffe_remote_config_activation(test_agent)

    @parametrize(
        "library_env",
        [{"configuration_source": "remote_config", "legacy_provider_enabled": False, "response": "valid"}],
        indirect=True,
    )
    def test_explicit_remote_config_wins_over_legacy_false(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    ) -> None:
        # DD_FEATURE_FLAGS_CONFIGURATION_SOURCE=remote_config conflicts intentionally with legacy
        # false, proving explicit stable source selection takes precedence over compatibility state.
        # RC ACK/capability and the expected evaluation prove RC is active, while zero mock requests
        # proves the available agentless endpoint is not consulted.
        apply_state = _set_and_wait_ffe_rc(test_agent, UFC_VALID_DATA)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert apply_state["product"] == RC_PRODUCT
        _assert_ffe_remote_config_activation(test_agent)

        assert test_library.ffe_start(), "failed to start explicit Remote Config provider"
        _assert_expected_value(_evaluate(test_library))
        _assert_no_mock_requests(mock_ffe_agentless_backend)

    @parametrize(
        "library_env",
        [{"configuration_source": None, "provider_enabled": False, "response": "valid"}],
        indirect=True,
    )
    def test_provider_kill_switch_stops_agentless_polling(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    ) -> None:
        # An absent source would normally choose default agentless, but DD_FEATURE_FLAGS_ENABLED=false
        # supplies the global override while a fully configured mock CDN remains reachable.
        # Zero mock requests and no FFE RC capability/product after provider access prove the stable
        # kill switch blocks both default CDN activation and any RC subscription.
        test_library.ffe_start()
        _assert_no_mock_requests(mock_ffe_agentless_backend)
        _assert_no_ffe_remote_config_activation(test_agent)

    @parametrize("library_env", [{"configuration_source": "invalid", "response": "valid"}], indirect=True)
    def test_invalid_configuration_source_fails_closed(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
    ) -> None:
        # An invalid explicit source tests configuration-error handling while valid agentless URL,
        # API-key, and response inputs ensure silence cannot be explained by an unavailable backend.
        # Zero mock requests and no FFE RC capability/product after provider access prove the SDK
        # fails closed instead of guessing a billed delivery path.
        test_library.ffe_start()
        _assert_no_mock_requests(mock_ffe_agentless_backend)
        _assert_no_ffe_remote_config_activation(test_agent)


@scenarios.parametric
@features.feature_flags_agentless
class Test_Feature_Flag_Configuration_Source_Cold_Failure_And_Recovery:
    """Validate cold-start failure and recovery behavior for agentless configuration source."""

    @parametrize(
        "library_env",
        [{"configuration_source": "agentless", "response": "valid", "api_key": None}],
        indirect=True,
    )
    def test_missing_auth_cold(
        self, test_library: APMLibrary, mock_ffe_agentless_backend: MockFFEAgentlessBackendServer
    ) -> None:
        # Explicit agentless plus api_key=None removes authentication without changing the valid base
        # URL or polling inputs, isolating authentication as the initial-load failure.
        # A 401/403 on CONFIG_PATH with no auth header proves the intended request was rejected, and
        # the default/not-ready evaluation proves unauthenticated bytes never initialize the provider.
        started = test_library.ffe_start()

        status = _wait_for_status(
            mock_ffe_agentless_backend,
            lambda current: current["last_status_code"] in {401, 403},
            "missing_auth_cold auth failure",
        )
        _assert_cold_not_ready(test_library, started=started)
        assert status["last_auth_present"] is False
        assert status["last_path"] == CONFIG_PATH

    @parametrize(
        "library_env",
        [{"configuration_source": "agentless", "response": "malformed"}],
        indirect=True,
    )
    def test_malformed_cold(
        self, test_library: APMLibrary, mock_ffe_agentless_backend: MockFFEAgentlessBackendServer
    ) -> None:
        # Explicit agentless with response=malformed keeps transport, authentication, and HTTP status
        # successful while making the first UFC payload invalid, isolating payload validation.
        # The authenticated 200 request to CONFIG_PATH proves delivery occurred, while the
        # default/not-ready evaluation proves malformed data was not installed.
        started = test_library.ffe_start()

        status = _wait_for_status(
            mock_ffe_agentless_backend,
            lambda current: current["requests_total"] > 0 and current["last_status_code"] == 200,
            "malformed_cold response",
        )
        _assert_cold_not_ready(test_library, started=started)
        assert status["last_auth_present"] is True
        assert status["last_path"] == CONFIG_PATH

    @parametrize(
        "library_env",
        [{"configuration_source": "agentless", "response": "timeout", "poll_interval": "5", "request_timeout": "1"}],
        indirect=True,
    )
    def test_request_timeout_cold(
        self, test_library: APMLibrary, mock_ffe_agentless_backend: MockFFEAgentlessBackendServer
    ) -> None:
        # response=timeout with a one-second request timeout and five-second poll interval makes the
        # first fetch exceed its per-request budget before another scheduled poll can interfere.
        # The observed CONFIG_PATH request proves the correct endpoint was attempted, while the
        # default/not-ready evaluation proves a timed-out cold fetch cannot initialize the provider.
        started = test_library.ffe_start()

        status = _wait_for_status(
            mock_ffe_agentless_backend,
            lambda current: current["requests_total"] > 0 and current["last_status_code"] == 200,
            "request_timeout_cold delayed valid response",
        )
        _assert_cold_not_ready(test_library, started=started)
        assert status["last_auth_present"] is True
        assert status["last_path"] == CONFIG_PATH

    @parametrize(
        ("library_env", "expected_status_codes"),
        [
            pytest.param(
                {"configuration_source": "agentless", "responses": ["server_error", "valid"]},
                [500, 200],
                id="server-error-to-valid",
            ),
        ],
        indirect=["library_env"],
    )
    def test_bad_to_good_cold_recovery(
        self,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
        expected_status_codes: list[int],
    ) -> None:
        # The explicit agentless response sequence [server_error, valid] drives a cold 500 followed by
        # a successful retry; expected_status_codes makes that transport order part of the test input.
        # Observing 500 then 200 proves retry behavior, and the expected evaluation plus CONFIG_PATH
        # prove the later valid UFC payload recovers an initially unready provider.
        assert test_library.ffe_start(), "failed to start FFE provider for bad_to_good"

        status = _wait_for_status(
            mock_ffe_agentless_backend,
            lambda current: _has_status_sequence(current["status_codes"], expected_status_codes),
            f"bad_to_good {expected_status_codes[0]} to 200 recovery",
        )
        _assert_expected_value(_evaluate(test_library))
        assert status["last_path"] == CONFIG_PATH

    @parametrize(
        ("library_env", "expected_status_codes"),
        [
            pytest.param(
                {"configuration_source": "agentless", "responses": ["server_error", "not_modified"]},
                [500, 304],
                id="server-error-to-unchanged",
            ),
        ],
        indirect=["library_env"],
    )
    def test_bad_to_unchanged_cold_preserves_not_ready(
        self,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
        expected_status_codes: list[int],
    ) -> None:
        # The explicit agentless sequence [server_error, not_modified] supplies a cold 500 followed by
        # 304 before any last-known-good configuration exists; expected_status_codes fixes that order.
        # Observing the sequence on CONFIG_PATH proves both polls occurred, while the default/not-ready
        # evaluation proves 304 cannot invent state after a failed initial load.
        started = test_library.ffe_start()

        status = _wait_for_status(
            mock_ffe_agentless_backend,
            lambda current: _has_status_sequence(current["status_codes"], expected_status_codes),
            f"bad_to_unchanged {expected_status_codes[0]} to 304 cold sequence",
        )
        _assert_cold_not_ready(test_library, started=started)
        assert status["last_path"] == CONFIG_PATH


@scenarios.parametric
@features.feature_flags_agentless
class Test_Feature_Flag_Configuration_Source_Warm_State_Preservation:
    """Validate that later agentless failures do not corrupt last-known-good state."""

    @parametrize("library_env", [{"configuration_source": "agentless", "response": "valid"}], indirect=True)
    def test_missing_auth_warm(
        self, test_library: APMLibrary, mock_ffe_agentless_backend: MockFFEAgentlessBackendServer
    ) -> None:
        # Explicit agentless with an initially valid response establishes last-known-good state before
        # the backend switches to unauthorized, isolating a later authentication failure.
        # The 401/403 and additional CONFIG_PATH request prove the failing poll occurred, while the
        # unchanged expected evaluation proves warm state survives the rejection.
        assert test_library.ffe_start(), "failed to start FFE provider before missing_auth_warm"
        _assert_expected_value(_evaluate(test_library))

        mock_ffe_agentless_backend.set_response("unauthorized")
        status = _wait_for_status(
            mock_ffe_agentless_backend,
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
                {"configuration_source": "agentless", "responses": ["valid", "server_error"]},
                [200, 500],
                id="valid-to-server-error",
            ),
        ],
        indirect=["library_env"],
    )
    def test_good_to_bad_warm_preservation(
        self,
        test_library: APMLibrary,
        mock_ffe_agentless_backend: MockFFEAgentlessBackendServer,
        expected_status_codes: list[int],
    ) -> None:
        # The explicit agentless response sequence [valid, server_error] creates last-known-good state
        # and then a 500; expected_status_codes makes the successful-to-failing transition observable.
        # The 200-to-500 sequence on CONFIG_PATH proves the failure followed a valid load, while the
        # expected evaluation proves the later server error did not replace warm state.
        assert test_library.ffe_start(), "failed to start FFE provider for good_to_bad"

        status = _wait_for_status(
            mock_ffe_agentless_backend,
            lambda current: _has_status_sequence(current["status_codes"], expected_status_codes),
            f"good_to_bad 200 to {expected_status_codes[1]} preservation",
        )
        _assert_expected_value(_evaluate(test_library))
        assert status["last_path"] == CONFIG_PATH

    @parametrize(
        "library_env", [{"configuration_source": "agentless", "responses": ["valid", "not_modified"]}], indirect=True
    )
    def test_good_to_unchanged_etag_sequence(
        self, test_library: APMLibrary, mock_ffe_agentless_backend: MockFFEAgentlessBackendServer
    ) -> None:
        # Explicit agentless responses [valid, not_modified] exercise conditional polling after a
        # successful load, making the fixture ETag and 304 behavior observable inputs.
        # The 200-to-304 sequence and If-None-Match value prove protocol reuse, while the expected
        # evaluation proves not-modified correctly preserves the installed configuration.
        assert test_library.ffe_start(), "failed to start FFE provider for good_to_unchanged"

        status = _wait_for_status(
            mock_ffe_agentless_backend,
            lambda current: _has_status_sequence(current["status_codes"], [200, 304])
            and current["last_if_none_match"] == '"ufc-v1"',
            "good_to_unchanged 200 to 304 ETag sequence",
        )
        _assert_expected_value(_evaluate(test_library))
        assert status["last_path"] == CONFIG_PATH

    @parametrize("library_env", [{"configuration_source": "agentless", "response": "valid"}], indirect=True)
    def test_malformed_warm(
        self, test_library: APMLibrary, mock_ffe_agentless_backend: MockFFEAgentlessBackendServer
    ) -> None:
        # Explicit agentless first loads valid UFC data, then the runtime response switch supplies a
        # malformed HTTP-200 payload so parsing failure is tested after initialization.
        # A higher request count and CONFIG_PATH prove the malformed poll occurred, while the unchanged
        # expected evaluation proves invalid bytes cannot replace last-known-good state.
        assert test_library.ffe_start(), "failed to start FFE provider before malformed_warm"
        _assert_expected_value(_evaluate(test_library))

        requests_before = mock_ffe_agentless_backend.status()["requests_total"]
        mock_ffe_agentless_backend.set_response("malformed")
        _wait_for_status(
            mock_ffe_agentless_backend,
            lambda current: (current["requests_total"] > requests_before and current["last_status_code"] == 200),
            "malformed_warm response",
        )
        _assert_expected_value(_evaluate(test_library))
        assert mock_ffe_agentless_backend.status()["last_path"] == CONFIG_PATH


@scenarios.parametric
@features.feature_flags_agentless
class Test_Feature_Flag_Configuration_Source_Poller_Concurrency:
    """Validate that agentless polling does not overlap requests under slow responses."""

    @parametrize("library_env", [{"configuration_source": "agentless", "response": "delayed_valid"}], indirect=True)
    def test_delayed_no_overlap(
        self, test_library: APMLibrary, mock_ffe_agentless_backend: MockFFEAgentlessBackendServer
    ) -> None:
        # Explicit agentless with response=delayed_valid makes a poll outlast the configured one-second
        # interval, creating the condition in which a timer-driven implementation might overlap calls.
        # A successful evaluation and CONFIG_PATH prove polling completed, while max_in_flight == 1
        # proves the poller serialized requests instead of starting a concurrent fetch.
        assert test_library.ffe_start(), "failed to start FFE provider for delayed_no_overlap"
        _assert_expected_value(_evaluate(test_library))

        status = _wait_for_status(
            mock_ffe_agentless_backend,
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
