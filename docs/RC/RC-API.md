The RC API is the official way to interact with remote config. It allows to send RC payload to the library durint setup phase, and send request before/after each state change.


## Sending command

Here is an example a scenario activating/deactivating ASM:

1. the library starts in an initial state where ASM is disabled. This state is validated with an assertion on a request containing an attack : the request should not been caught by ASM
2. Then a RC command is sent to activate ASM
3. another request containing an attack is sent, this one must be reported by ASM
4. A second command is sent to deactivate ASM
5. a thirst request containing an attack is sent, this last one should not be seen


Here is the test code performing that test. Please note variables `activate_ASM_command` and `deactivate_ASM_command`: see the next paragrpah to understand how to build them.

```python
from utils import weblog, interfaces, scenarios, remote_config


@scenarios.asm_deactivated  # in this scenario, ASM is deactivated
class Test_RemoteConfigSequence:
    """ Test that ASM can be activated/deacrivated using Remote Config """

    def setup_asm_switch_on_switch_off(self):
        # at initiation, ASM is disabled
        self.first_request = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

        # this function will send a RC payload to the library, and wait for a confirmation from the library
        self.config_states_activation = activate_ASM_command.send()
        self.second_request = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

        # now deactivate the WAF, and check that it does not catch anything
        self.config_states_deactivation = deactivate_ASM_command.send()
        self.third_request = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_asm_switch_on_switch_off():
        # first check that both config state are ok, otherwise, next assertions will fail with cryptic messages
        assert self.config_states_activation["asm_features_activation"]["apply_state"] == remote_config.ApplyState.ACKNOWLEDGED, self.config_states_activation
        assert self.config_states_deactivation["asm_features_activation"]["apply_state"] == remote_config.ApplyState.ACKNOWLEDGED, self.config_states_deactivation

        interfaces.library.assert_no_appsec_event(self.first_request)
        interfaces.library.assert_waf_attack(self.second_request)
        interfaces.library.assert_no_appsec_event(self.third_request)
```

To use this feature, you must use an `EndToEndScenario` with `rc_api_enabled=True`.

## Crafting commands

Building remote config command is not an easy task. System-tests provides an high level API that allow you to easily craft those commands. Here is an example :


``` python
from utils import remote_config, interfaces


class Test_RemoteConfig:
    BLOCKED_IP = "1.2.3.4"

    def setup_main(self):
        config = {
            "rules_data": [
                {
                    "id": "blocked_ips",
                    "type": "ip_with_expiration",
                    "data": [{"value": BLOCKED_IP, "expiration": 9999999999}],
                },
            ]
        }

        command = remote_config.RemoteConfigCommand(version=self.TARGETS_VERSION)
        command.add_client_config("datadog/2/ASM_DATA/ASM_DATA-base/config", config)

        command.send()

        self.blocked_request = weblog.get(headers={"X-Forwarded-For": BLOCKED_IP})

    def test_main(self):
        interfaces.library.assert_rc_apply_state("ASM_DATA-base", "ASM_DATA", RemoteConfigApplyState.ACKNOWLEDGED)
        assert self.blocked_request.status_code == 403
        interfaces.library.assert_waf_attack(self.blocked_request)
```

