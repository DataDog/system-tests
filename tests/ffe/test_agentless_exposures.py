"""Test exposure events when UFC is loaded through the default agentless source."""

from tests.ffe.test_exposures import EXPOSURES_PATH, exposure_events_from_data
from tests.ffe.utils.evaluation import evaluate_flag
from tests.ffe.utils.fixtures import JSON
from tests.ffe.utils.telemetry import (
    UNEXPECTED_ROUTE_WAIT_SECONDS,
    assert_expected_telemetry_route,
    matching_telemetry,
    telemetry_request_was_accepted,
    wait_for_telemetry,
)
from utils import context, features, interfaces, scenarios
from utils.interfaces._feature_flag_telemetry import FeatureFlagTelemetryInterfaceValidator


RELAY_EXPOSURES_PATH_V4 = "/evp_proxy/v4/api/v2/exposures"
RELAY_EXPOSURES_PATH_V2 = "/evp_proxy/v2/api/v2/exposures"


@scenarios.feature_flagging_and_experimentation_agentless_sidecar
@scenarios.feature_flagging_and_experimentation_agentless_in_process
@scenarios.feature_flagging_and_experimentation_agentless_direct_fallback
@features.feature_flags_exposures
class Test_FFE_Agentless_Exposure:
    flag_key = "empty-targeting-key-flag"
    targeting_key = "agentless-exposure-user"

    def setup_agentless_exposure(self) -> None:
        self.response = evaluate_flag(self.flag_key, targeting_key=self.targeting_key)

    def test_agentless_exposure(self) -> None:
        assert self.response.status_code == 200, f"Flag evaluation failed: {self.response.text}"

        def matcher(data: JSON) -> bool:
            return bool(exposure_events_from_data(data, {self.flag_key}, self.targeting_key))

        wait_for_telemetry(matcher, "exposure event")

        events = []
        for data in matching_telemetry(matcher):
            if data.get("path") == EXPOSURES_PATH:
                events.extend(exposure_events_from_data(data, {self.flag_key}, self.targeting_key))
        assert len(events) == 1, (
            f"Expected one exposure event for {self.flag_key} and {self.targeting_key}, got {len(events)}"
        )
        assert_expected_telemetry_route(matcher, "exposure event")

        event = events[0]
        assert event["flag"]["key"] == self.flag_key
        assert event["variant"]["key"] == "on"
        assert event["allocation"]["key"] == "default-allocation"
        assert event["subject"]["id"] == self.targeting_key


def _exposure_events_from_any_route(data: JSON, flag_key: str, targeting_key: str) -> list[JSON]:
    path = data.get("path")
    if not isinstance(path, str) or not path.endswith(EXPOSURES_PATH):
        return []

    canonical = dict(data)
    canonical["path"] = EXPOSURES_PATH
    return exposure_events_from_data(canonical, {flag_key}, targeting_key)


def _evaluate_discovery_flag(flag_key: str, targeting_key: str) -> None:
    response = evaluate_flag(flag_key, targeting_key=targeting_key)
    assert response.status_code == 200, f"Flag evaluation failed: {response.text}"


def _matching_exposure_requests(
    interface: FeatureFlagTelemetryInterfaceValidator, flag_key: str, targeting_key: str
) -> list[JSON]:
    return [data for data in interface.get_data() if _exposure_events_from_any_route(data, flag_key, targeting_key)]


@scenarios.feature_flagging_and_experimentation_agentless_relay_v4
@scenarios.feature_flagging_and_experimentation_agentless_relay_v2
@features.feature_flags_exposures
class Test_FFE_Agentless_Exposure_Discovery:
    flag_key = "empty-targeting-key-flag"
    targeting_key = "agentless-discovery-user"

    def setup_agentless_exposure_prefers_advertised_local_evp(self) -> None:
        _evaluate_discovery_flag(self.flag_key, self.targeting_key)

    def test_agentless_exposure_prefers_advertised_local_evp(self) -> None:
        relay_profile = getattr(context.scenario, "relay_profile")  # noqa: B009 - scenario subtype capability
        expected_path = {
            "v4": RELAY_EXPOSURES_PATH_V4,
            "v2": RELAY_EXPOSURES_PATH_V2,
        }[relay_profile]

        assert interfaces.ffe_relay.wait_for(
            lambda data: data.get("path") == expected_path
            and bool(_exposure_events_from_any_route(data, self.flag_key, self.targeting_key)),
            timeout=30,
        ), f"Timed out waiting for exposure through advertised {relay_profile} EVP route"

        relay_requests = _matching_exposure_requests(interfaces.ffe_relay, self.flag_key, self.targeting_key)
        accepted = [data for data in relay_requests if telemetry_request_was_accepted(data)]
        assert len(accepted) == 1, f"Expected one accepted local exposure request, got {len(accepted)}"
        assert accepted[0]["path"] == expected_path
        assert list(interfaces.ffe_relay.get_data(path_filters="/info")), "Tracer did not discover relay capabilities"
        assert not _matching_exposure_requests(interfaces.ffe_direct, self.flag_key, self.targeting_key)


@scenarios.feature_flagging_and_experimentation_agentless_relay_no_evp
@features.feature_flags_exposures
class Test_FFE_Agentless_Exposure_PreSend_Fallback:
    flag_key = "empty-targeting-key-flag"
    targeting_key = "agentless-no-evp-user"

    def setup_agentless_exposure_falls_back_when_info_has_no_evp(self) -> None:
        _evaluate_discovery_flag(self.flag_key, self.targeting_key)

    def test_agentless_exposure_falls_back_when_info_has_no_evp(self) -> None:
        def matcher(data: JSON) -> bool:
            return bool(_exposure_events_from_any_route(data, self.flag_key, self.targeting_key))

        wait_for_telemetry(matcher, "direct exposure after unsupported /info")
        assert_expected_telemetry_route(matcher, "direct exposure after unsupported /info")
        assert list(interfaces.ffe_relay.get_data(path_filters="/info")), "Tracer did not query relay /info"
        assert not _matching_exposure_requests(interfaces.ffe_relay, self.flag_key, self.targeting_key)


@scenarios.feature_flagging_and_experimentation_agentless_relay_evp_405
@features.feature_flags_exposures
class Test_FFE_Agentless_Exposure_Definitive_Fallback:
    flag_key = "empty-targeting-key-flag"
    targeting_key = "agentless-evp-405-user"

    def setup_agentless_exposure_retries_direct_after_405(self) -> None:
        _evaluate_discovery_flag(self.flag_key, self.targeting_key)

    def test_agentless_exposure_retries_direct_after_405(self) -> None:
        def matcher(data: JSON) -> bool:
            return bool(_exposure_events_from_any_route(data, self.flag_key, self.targeting_key))

        assert interfaces.ffe_relay.wait_for(
            lambda data: matcher(data) and data.get("response", {}).get("status_code") == 405,
            timeout=30,
        ), "Timed out waiting for the definitive local EVP 405"
        wait_for_telemetry(matcher, "direct exposure after local EVP 405")
        assert_expected_telemetry_route(matcher, "direct exposure after local EVP 405")

        local_attempts = _matching_exposure_requests(interfaces.ffe_relay, self.flag_key, self.targeting_key)
        direct_accepts = [
            data
            for data in _matching_exposure_requests(interfaces.ffe_direct, self.flag_key, self.targeting_key)
            if telemetry_request_was_accepted(data)
        ]
        assert len(local_attempts) == 1, f"Expected one local attempt before fallback, got {len(local_attempts)}"
        assert len(direct_accepts) == 1, f"Expected one accepted direct fallback, got {len(direct_accepts)}"


@scenarios.feature_flagging_and_experimentation_agentless_relay_evp_500
@features.feature_flags_exposures
class Test_FFE_Agentless_Exposure_Ambiguous_Failure:
    flag_key = "empty-targeting-key-flag"
    targeting_key = "agentless-evp-500-user"

    def setup_agentless_exposure_does_not_retry_direct_after_500(self) -> None:
        _evaluate_discovery_flag(self.flag_key, self.targeting_key)

    def test_agentless_exposure_does_not_retry_direct_after_500(self) -> None:
        def matcher(data: JSON) -> bool:
            return bool(_exposure_events_from_any_route(data, self.flag_key, self.targeting_key))

        assert interfaces.ffe_relay.wait_for(
            lambda data: matcher(data) and data.get("response", {}).get("status_code") == 500,
            timeout=30,
        ), "Timed out waiting for the ambiguous local EVP 500"
        assert not interfaces.ffe_direct.wait_for(matcher, timeout=UNEXPECTED_ROUTE_WAIT_SECONDS), (
            "Ambiguously rejected local exposure was retried through direct intake"
        )
