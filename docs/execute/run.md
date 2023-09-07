`run.sh` accepts several options:

## Run all tests

```bash
./run.sh
```

## Run only one file

```bash
./run.sh tests/test_waf.py
```

## Run only one class, or one method

```bash
./run.sh tests/test_waf.py::Test_WAFAddresses

# and one method:
./run.sh tests/test_waf.py::Test_WAFAddresses::test_post_json_value
```

## Run a scenario

Without providing a scenario argument, only the tests without any `@scenario` decorator will be executed. We provide a scenario name to `run.sh` to run tests decorated with the given scenario.

```bash
./run.sh <SCENARIO_ENV_VAR>
# e.g, "LIBRARY_CONF_CUSTOM_HEADERS_LONG" to run the library_conf_custom_headers_long scenario
```

## Spawn componenents, but do nothing

```bash
./run.sh SLEEP

# play with the weblog, and look inside logs/interfaces/ what's happening
```
