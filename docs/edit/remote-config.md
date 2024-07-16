The RC API is the official way to interact with remote config. It allows to build and send RC payloads to the library durint setup phase, and send request before/after each state change.

## Building RC payload

### Example

``` python
from utils import remote_config


# will return the command associated to the current scenario
command = remote_config.RemoteConfigCommand()

config = {
    "rules_data": [
        {
            "id": "blocked_ips",
            "type": "ip_with_expiration",
            "data": [{"value": BLOCKED_IP, "expiration": 9999999999}],
        },
    ]
}

command.add_client_config(f"datadog/2/ASM_DATA-base/ASM_DATA-base/config", config)
# send the command and wait for the result to be validated by the tracer
command.send()
```

### API

#### class `remote_config.RemoteConfigCommand`

This class will be serialized as a valid `ClientGetConfigsResponse`.

* constructor `__init__(self, expires=None)`
  * `expires` [optional]: expiration date of the config (default `3000-01-01T00:00:00Z`)
* `add_client_config(self, path, config) -> ClientConfig`
  * `path`: configuration path
  * `config`: config object
* `del_client_config(self, path) -> ClientConfig`
  * `path`: configuration path
* `reset(self) -> ClientConfig`
* `send()`: send the command using the `send_command` function (see below)


## Sending command

### Example

Here is an example a scenario activating/deactivating ASM:

1. the library starts in an initial state where ASM is disabled. This state is validated with an assertion on a request containing an attack : the request should not been caught by ASM
2. Then a RC command is sent to activate ASM
3. another request containing an attack is sent, this one must be reported by ASM
4. A second command is sent to deactivate ASM
5. a thirst request containing an attack is sent, this last one should not be seen


Here is the test code performing that test. Please note variables `activate_ASM_command` and `deactivate_ASM_command`: see the previous paragraph to understand how to build them.

```python
from utils import weblog, interfaces, scenarios, remote_config


@scenarios.asm_deactivated  # in this scenario, ASM is deactivated
class Test_RemoteConfigSequence:
    """ Test that ASM can be activated/deacrivated using Remote Config """

    def setup_asm_switch_on_switch_off(self):
        # at initiation, ASM is disabled
        self.first_request = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

        # this function will send a RC payload to the library, and wait for a confirmation from the library
        self.config_states_activation = command.add_client_config(path, asm_enabled).send()
        self.second_request = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

        # now deactivate the WAF by deleting the RC file, and check that it does not catch anything
        self.config_states_deactivation = command.del_client_config(path).send()
        self.third_request = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_asm_switch_on_switch_off():
        # first check that both config state are ok, otherwise, next assertions will fail with cryptic messages
        assert self.config_states_activation["asm_features_activation"]["apply_state"] == remote_config.ApplyState.ACKNOWLEDGED, self.config_states_activation
        assert self.config_states_activation.state == remote_config.ApplyState.ACKNOWLEDGED
        # the config is empty, you can just check for it to be properly acknowledged
        assert self.config_states_deactivation.state == remote_config.ApplyState.ACKNOWLEDGED

        interfaces.library.assert_no_appsec_event(self.first_request)
        interfaces.library.assert_waf_attack(self.second_request)
        interfaces.library.assert_no_appsec_event(self.third_request)
```

To use this feature, you must use an `EndToEndScenario` with `rc_api_enabled=True`.

### API

#### `send_command(raw_payload, *, wait_for_acknowledged_status: bool = True) -> dict[str, dict[str, Any]]`

Sends a remote config payload to the library and waits for the config to be applied.
Then returns a dictionary with the state of each requested file as returned by the library.

The dictionary keys are the IDs from the files that can be extracted from the path,
e.g: datadog/2/ASM_FEATURES/asm_features_activation/config => asm_features_activation
and the values contain the actual state for each file:

1. a config state acknowledging the config
2. else if not acknowledged, the last config state received
3. if no config state received, then a hardcoded one with apply_state=UNKNOWN

Arguments:
    wait_for_acknowledge_status
        If True, waits for the config to be acknowledged by the library.
        Else, only wait for the next request sent to /v0.7/config

## Assertions

During the test phase `interfaces.library` offers some helpers to perform high level assertions

### `interfaces.library.assert_rc_apply_state`

Check that all config_id/product have the expected apply_state returned by the library
Very simplified version of the assert_rc_targets_version_states

* `product`: product part of the configuration path
* `config_id`: config_id part of the configuration path
* `apply_state`: expected apply_state for this config.


### `interfaces.library.assert_rc_targets_version_states`

Check that for a given targets_version, the config states is the one expected

Example :

``` python
interfaces.library.assert_rc_targets_version_states(
    targets_version=self.TARGETS_VERSION,
    config_states=[
        {
            "id": "ASM_DATA-base",
            "version": 1,
            "product": "ASM_DATA",
            "apply_state": RemoteConfigApplyState.ACKNOWLEDGED.value,
        }
    ],
)
```
