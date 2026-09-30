"""Test one exposure contract through every supported deployment topology."""

from tests.ffe.utils.evp import (
    assert_agentless_evp_intake_request,
    assert_agentless_evp_topology,
    assert_direct_evp_shutdown_evidence,
    feature_flagging_evp_egress,
    register_expected_evp_capture,
    register_shutdown_evp_evaluation,
)
from tests.ffe.utils.exposures import (
    EXPOSURES_PATH,
    assert_exposure_side_effects_contract,
    exposure_events_from_data,
)
from tests.ffe.utils.fixtures import make_ufc_fixture
from utils import context, features, remote_config as rc, scenario_crash, scenarios, weblog
from utils._context._scenarios.agentless_endtoend import FeatureFlaggingAgentlessEndToEndScenario

RC_PATH = "datadog/2/FFE_FLAGS"


class ExposureEgressContract:
    """One exposure contract inherited by each supported topology adapter."""

    flag_key = "empty-targeting-key-flag"
    targeting_key = "exposure-egress-user"

    def setup_exposure_egress(self) -> None:
        register_expected_evp_capture(EXPOSURES_PATH)
        if not isinstance(context.scenario, FeatureFlaggingAgentlessEndToEndScenario):
            rc.tracer_rc_state.reset().set_config(
                f"{RC_PATH}/exposure-egress/config",
                make_ufc_fixture(self.flag_key),
            ).apply()

        self.responses = [
            weblog.post(
                "/ffe",
                json={
                    "flag": self.flag_key,
                    "variationType": "STRING",
                    "defaultValue": "default",
                    "targetingKey": self.targeting_key,
                    "attributes": {},
                },
            )
            for _ in range(5)
        ]

    def test_exposure_egress(self) -> None:
        egress = feature_flagging_evp_egress()
        matching_requests = assert_exposure_side_effects_contract(
            egress.interface,
            self.responses,
            flag_key=self.flag_key,
            targeting_key=self.targeting_key,
            expected_value="on-value",
            expected_variant="on",
        )
        assert len(matching_requests) == 1
        assert_agentless_evp_topology(egress)

        if egress.expected_api_key is None:
            return

        for request in matching_requests:
            assert_agentless_evp_intake_request(
                request,
                route=egress.route,
                path=EXPOSURES_PATH,
                expected_api_key=egress.expected_api_key,
                library_name=context.library.name,
                library_version=context.library.raw_version,
            )

        for excluded_interface in egress.excluded_interfaces:
            assert not any(
                exposure_events_from_data(data, {self.flag_key}, self.targeting_key)
                for data in excluded_interface.get_data()
            )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_exposures
class Test_FFE_Exposure_Egress_Datadog_Agent(ExposureEgressContract):
    pass


@scenario_crash
@scenarios.feature_flagging_and_experimentation_agentless_direct
@features.feature_flags_exposures
class Test_FFE_Exposure_Egress_Agentless_Direct(ExposureEgressContract):
    pass


@scenario_crash
@scenarios.feature_flagging_and_experimentation_agentless_direct
@features.feature_flags_exposures
class Test_FFE_Exposure_Egress_Agentless_Direct_Shutdown:
    """Prove a just-produced exposure is flushed by runtime shutdown, not a pre-stop wait."""

    flag_key = "empty-targeting-key-flag"
    targeting_key = "exposure-shutdown-user"

    def setup_exposure_egress_shutdown(self) -> None:
        register_shutdown_evp_evaluation(
            signal_path=EXPOSURES_PATH,
            request_path="/ffe",
            body={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": self.targeting_key,
                "attributes": {},
            },
            flag_key=self.flag_key,
            subject_id=self.targeting_key,
        )

    def test_exposure_egress_shutdown(self) -> None:
        egress = feature_flagging_evp_egress()
        assert egress.route == "direct"
        assert_agentless_evp_topology(egress)

        scenario = context.scenario
        assert isinstance(scenario, FeatureFlaggingAgentlessEndToEndScenario)
        assert_direct_evp_shutdown_evidence(scenario.direct_evp_shutdown_evidence())

        matching_requests = [
            data
            for data in egress.interface.get_data()
            if exposure_events_from_data(data, {self.flag_key}, self.targeting_key)
        ]
        assert len(matching_requests) == 1
        events = exposure_events_from_data(matching_requests[0], {self.flag_key}, self.targeting_key)
        assert len(events) == 1
        event = events[0]
        assert event["flag"]["key"] == self.flag_key
        assert event["variant"]["key"] == "on"
        assert event["allocation"]["key"] == "default-allocation"
        assert event["subject"]["id"] == self.targeting_key
        batch_context = matching_requests[0]["request"]["content"]["context"]
        assert batch_context == {
            "env": "system-tests",
            "service": "weblog",
            "version": "1.0.0",
        }

        assert egress.expected_api_key is not None
        assert_agentless_evp_intake_request(
            matching_requests[0],
            route=egress.route,
            path=EXPOSURES_PATH,
            expected_api_key=egress.expected_api_key,
            library_name=context.library.name,
            library_version=context.library.raw_version,
        )
        for excluded_interface in egress.excluded_interfaces:
            assert not any(
                exposure_events_from_data(data, {self.flag_key}, self.targeting_key)
                for data in excluded_interface.get_data()
            )


@scenario_crash
@scenarios.feature_flagging_and_experimentation_agentless_serverless
@features.feature_flags_exposures
class Test_FFE_Exposure_Egress_Agentless_Sidecar(ExposureEgressContract):
    pass
