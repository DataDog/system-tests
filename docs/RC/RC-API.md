The RC API is the official way to interact with remote config. It allows to send RC payload to the library durint setup phase, and send request before/after each state change. Here is an example a scenario activating/deactivating ASM:

1. the library starts in an initial state where ASM is disabled. This state is validated with an assertion on a request containing an attack : the request should not been caught by ASM
2. Then a RC command is sent to activate ASM
3. another request containing an attack is sent, this one must be reported by ASM
4. A second command is sent to deactivate ASM
5. a thirst request containing an attack is sent, this last one should not be seen


Here is the test code performing that test. Please note the magic constants `ACTIVATE_ASM_PAYLOAD` and `DEACTIVATE_ASM_PAYLOAD`: they are encoded RC payload (exemple [here](https://github.com/DataDog/system-tests/blob/7644ceaa3c7ea44ade8bcca8c3bb2a5991d03e34/utils/proxy/rc_mocked_responses_asm_activate_only.json)). We still miss a tool that generate them from human-readable content, it will come in a near future.

```python
from utils import weblog, interfaces, scenarios, remote_config


@scenarios.asm_deactivated  # in this scenario, ASM is deactivated
class Test_RemoteConfigSequence:
    """ Test that ASM can be activated/deacrivated using Remote Config """

    def setup_asm_switch_on_switch_off(self):
        # at initiation, ASM is disabled
        self.first_request = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

        # this function will send a RC payload to the library, and wait for a confirmation from the library
        self.config_state_activation = remote_config.send_command(raw_payload=ACTIVATE_ASM_PAYLOAD)
        self.second_request = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

        # now deactivate the WAF, and check that it does not catch anything
        self.config_state_deactivation = remote_config.send_command(raw_payload=DEACTIVATE_ASM_PAYLOAD)
        self.third_request = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_asm_switch_on_switch_off():
        # first check that both config state are ok, otherwise, next assertions will fail with cryptic messages
        assert self.config_state_activation["apply_state"] == remote_config.ApplyState.ACKNOWLEDGED, self.config_state_activation
        assert self.config_state_deactivation["apply_state"] == remote_config.ApplyState.ACKNOWLEDGED, self.config_state_deactivation

        interfaces.library.assert_no_appsec_event(self.first_request)
        interfaces.library.assert_waf_attack(self.second_request)
        interfaces.library.assert_no_appsec_event(self.third_request)
```

To use this feature, you must use an `EndToEndScenario` with `rc_api_enabled=True`.
