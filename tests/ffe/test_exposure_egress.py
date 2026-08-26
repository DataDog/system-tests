"""Test one exposure contract through every supported deployment topology."""

import json
import time
from dataclasses import dataclass

from tests.ffe.utils.exposures import (
    EXPOSURE_WAIT_TIMEOUT_SECONDS,
    assert_exposure_side_effects_contract,
    exposure_events_from_data,
)
from tests.ffe.utils.fixtures import make_ufc_fixture
from utils import context, features, interfaces, remote_config as rc, scenarios, weblog
from utils._context._scenarios.agentless_endtoend import FeatureFlaggingAgentlessEndToEndScenario
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils.mocked_backend.ffe import EXPECTED_API_KEY

RC_PATH = "datadog/2/FFE_FLAGS"
EXPECTED_API_KEY_FINGERPRINT = "rijn_Fc1Sxm6lPHiKU1IdWeNqpcVZiiW3C2LXJLqQp670sFU"


@dataclass(frozen=True)
class ExposureEgress:
    interface: ProxyBasedInterfaceValidator
    excluded_interfaces: tuple[ProxyBasedInterfaceValidator, ...] = ()
    expected_api_key: str | None = None
    expected_api_key_fingerprint: str | None = None


def exposure_egress() -> ExposureEgress:
    """Return the capture interface and route-only expectations for this topology."""
    scenario = context.scenario
    if not isinstance(scenario, FeatureFlaggingAgentlessEndToEndScenario):
        assert scenario.name == "FEATURE_FLAGGING_AND_EXPERIMENTATION"
        return ExposureEgress(interfaces.agent)

    if scenario.exposure_egress == "sidecar":
        assert "serverless-init" in scenario.components
        expected_api_key = scenario.serverless_init_container.environment["DD_API_KEY"]
        assert expected_api_key is not None
        return ExposureEgress(
            interfaces.datadog_sidecar,
            (interfaces.datadog_direct,),
            expected_api_key,
        )

    assert scenario.exposure_egress == "direct"
    assert "serverless-init" not in scenario.components
    return ExposureEgress(
        interfaces.datadog_direct,
        (interfaces.datadog_sidecar,),
        EXPECTED_API_KEY,
        EXPECTED_API_KEY_FINGERPRINT,
    )


class ExposureEgressContract:
    """One exposure contract inherited by each supported topology adapter."""

    flag_key = "empty-targeting-key-flag"
    targeting_key = "exposure-egress-user"

    def evaluate_flag(self):
        return weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
        )

    def setup_exposure_egress(self) -> None:
        if not isinstance(context.scenario, FeatureFlaggingAgentlessEndToEndScenario):
            rc.tracer_rc_state.reset().set_config(
                f"{RC_PATH}/exposure-egress/config",
                make_ufc_fixture(self.flag_key),
            ).apply()

        # The Agent delivers remote configuration asynchronously. Wait until the fixture
        # observes the expected value before collecting responses for the strict contract.
        deadline = time.monotonic() + EXPOSURE_WAIT_TIMEOUT_SECONDS
        while True:
            response = self.evaluate_flag()
            if response.status_code == 200 and json.loads(response.text)["value"] == "on-value":
                break
            assert time.monotonic() < deadline, f"Timed out waiting for {self.flag_key!r} to evaluate to 'on-value'"
            time.sleep(0.25)

        self.responses = [self.evaluate_flag() for _ in range(5)]

        # Agentless targets are stopped immediately after setup, before test assertions run.
        # Keep the target alive until buffered SDK writers have flushed to the selected route.
        egress = exposure_egress()
        assert egress.interface.wait_for(
            lambda data: bool(exposure_events_from_data(data, {self.flag_key}, self.targeting_key)),
            timeout=EXPOSURE_WAIT_TIMEOUT_SECONDS,
        ), f"Timed out waiting for exposure event for {self.flag_key!r} and {self.targeting_key!r}"

    def test_exposure_egress(self) -> None:
        egress = exposure_egress()
        matching_requests = assert_exposure_side_effects_contract(
            egress.interface,
            self.responses,
            flag_key=self.flag_key,
            targeting_key=self.targeting_key,
            expected_value="on-value",
            expected_variant="on",
        )
        assert len(matching_requests) == 1

        if egress.expected_api_key is None:
            return

        request = matching_requests[0]
        assert request["host"] == "event-platform-intake.mock-intake.invalid"
        assert request["response"]["status_code"] == 202

        headers = {name.lower(): value for name, value in request["request"]["headers"]}
        assert headers["dd-api-key"] in {egress.expected_api_key, "--redacted--"}
        if egress.expected_api_key_fingerprint is not None:
            assert headers["dd-api-key-fingerprint"] == egress.expected_api_key_fingerprint

        for excluded_interface in egress.excluded_interfaces:
            assert not any(
                exposure_events_from_data(data, {self.flag_key}, self.targeting_key)
                for data in excluded_interface.get_data()
            )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_exposures
class Test_FFE_Exposure_Egress_Datadog_Agent(ExposureEgressContract):
    pass


@scenarios.feature_flagging_and_experimentation_agentless_direct
@features.feature_flags_exposures
class Test_FFE_Exposure_Egress_Agentless_Direct(ExposureEgressContract):
    pass


@scenarios.feature_flagging_and_experimentation_agentless_serverless
@features.feature_flags_exposures
class Test_FFE_Exposure_Egress_Agentless_Sidecar(ExposureEgressContract):
    pass
