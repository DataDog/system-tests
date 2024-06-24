## How to create tests with new Remote Config

### Create new scenario

To run tests with custom Remote Config, you need to create new scenario with a mocked RC responses.

```python
appsec_api_security_rc = EndToEndScenario(
    "APPSEC_API_SECURITY_RC",
    proxy_state={"mock_remote_config_backend": "APPSEC_API_SECURITY_RC"},
    doc="""
        Scenario to test API Security Remote config
    """,
)
```

In this code example, we can see that we are defining a proxy for remote config, with the name **APPSEC_API_SECURITY_RC**,
it means that this scenario will mock calls from libraries to `/v7/config` by the content in *utils/proxy/rc_mocked_responses\_**appsec_api_security_rc**.json* file.

### Create mock file

`utils/proxy/rc_mocked_responses_<defined_mock_rc_backend_name>.json` JSON file contains an array with a list of the responses that config url will return. The items are returned in order, first time it returns the first element in the list, and each time the request is made, it returns the next value in the list.

There is a repository [RC tracer client test generator](https://github.com/DataDog/rc-tracer-client-test-generator) that you can use to generate RC files.

### Wait to RC loaded

In your tests, you should wait until the RC is loaded. If your mock list only have one item, you can use this method to wait until RC is loaded to start executing the requests.

```python
interfaces.library.wait_for_remote_config_request()
```

If you have more configs in the list, and you need to wait to one specific config, you can until the file that you need is loaded, for example, it is done in [blocked ips system test](https://github.com/DataDog/system-tests/blob/72f8b47d014977fb4cd63c64bb1f8340e01dec05/tests/appsec/test_ip_blocking_full_denylist.py#L56-L68).

```python
def remote_config_is_applied(data):
    if data["path"] == "/v0.7/config":
        if "config_states" in data.get("request", {}).get("content", {}).get("client", {}).get("state", {}):
            config_states = data["request"]["content"]["client"]["state"]["config_states"]

            for state in config_states:
                if state["id"] == "ASM_DATA-third":
                    return True

    return False

interfaces.library.wait_for(remote_config_is_applied, timeout=30)
```
