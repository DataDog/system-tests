from utils import remote_config, interfaces
from utils.dd_constants import RemoteConfigApplyState


class BaseFullDenyListTest:
    states = None

    def setup_scenario(self):
        # Generate the list of 100 * 125 = 12500 blocked ips that are found in the rc_mocked_responses_asm_data_full_denylist.json
        # to edit or generate a new rc mocked response, use the DataDog/rc-tracer-client-test-generator repository
        BLOCKED_IPS = [f"12.8.{a}.{b}" for a in range(100) for b in range(125)]

        if BaseFullDenyListTest.states is None:
            config = {
                "rules_data": [
                    {
                        "id": "blocked_ips",
                        "type": "ip_with_expiration",
                        "data": [{"value": ip, "expiration": 9999999999} for ip in BLOCKED_IPS],
                    },
                    {
                        "id": "blocked_users",
                        "type": "data_with_expiration",
                        "data": [{"value": str(value), "expiration": 9999999999} for value in range(2500)],
                    },
                ]
            }

            command = remote_config.RemoteConfigCommand()
            command.add_client_config("datadog/2/ASM_DATA/ASM_DATA-base/config", config)

            BaseFullDenyListTest.states = command.send()

        self.states = BaseFullDenyListTest.states
        self.blocked_ips = [BLOCKED_IPS[0], BLOCKED_IPS[2500], BLOCKED_IPS[-1]]

    def assert_protocol_is_respected(self):
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
