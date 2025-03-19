from utils import interfaces
from utils import remote_config
from utils.dd_constants import RemoteConfigApplyState


def find_series(request_type, namespace, metrics) -> list:
    series = []
    for data in interfaces.library.get_telemetry_data():
        content = data["request"]["content"]
        if content.get("request_type") != request_type:
            continue
        fallback_namespace = content["payload"].get("namespace")
        for serie in content["payload"]["series"]:
            computed_namespace = serie.get("namespace", fallback_namespace)
            if computed_namespace == namespace and serie["metric"] in metrics:
                series.append(serie)
    return series


class BaseFullDenyListTest:
    states = None

    def setup_scenario(self) -> None:
        # Generate the list of 100 * 125 = 12500 blocked ips that are found in the
        # file rc_mocked_responses_asm_data_full_denylist.json
        # to edit or generate a new rc mocked response, use the DataDog/rc-tracer-client-test-generator repository
        blocked_ips = [f"12.8.{a}.{b}" for a in range(100) for b in range(125)]

        if BaseFullDenyListTest.states is None:
            config = {
                "rules_data": [
                    {
                        "id": "blocked_ips",
                        "type": "ip_with_expiration",
                        "data": [{"value": ip, "expiration": 9999999999} for ip in blocked_ips],
                    },
                    {
                        "id": "blocked_users",
                        "type": "data_with_expiration",
                        "data": [{"value": str(value), "expiration": 9999999999} for value in range(2500)],
                    },
                ]
            }

            rc_state = remote_config.rc_state
            rc_state.set_config("datadog/2/ASM_DATA/ASM_DATA-base/config", config)

            BaseFullDenyListTest.states = rc_state.apply()

        self.states = BaseFullDenyListTest.states
        self.blocked_ips = [blocked_ips[0], blocked_ips[2500], blocked_ips[-1]]

    def assert_protocol_is_respected(self) -> None:
        interfaces.library.assert_rc_targets_version_states(targets_version=0, config_states=[])
        interfaces.library.assert_rc_targets_version_states(
            targets_version=self.states[remote_config.RC_VERSION],
            config_states=[
                {
                    "id": "ASM_DATA-base",
                    "version": 1,
                    "product": "ASM_DATA",
                    "apply_state": RemoteConfigApplyState.ACKNOWLEDGED.value,
                }
            ],
        )
