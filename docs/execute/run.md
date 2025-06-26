`run.sh` accepts several options:

## Run all tests using the DEFAULT scenario

```bash
./run.sh
```

## Run only one file

```bash
./run.sh tests/test_waf.py
```

If the test contains `@scenarios.SCENARIO_NAME` such as `@scenarios.integrations`, then the `./run.sh` needs to be adjusted to the following:

```bash
./run.sh SCENARIO_NAME tests/path_to_test.py

# Example: for @scenarios.integrations in tests/integrations/test_sql.py
./run.sh INTEGRATIONS tests/integrations/test_sql.py
```

## Run only one class, or one method

```bash
./run.sh tests/parametric/test_waf.py::Test_WAFAddresses

# and one method:
./run.sh tests/parametric/test_waf.py::Test_WAFAddresses::test_post_json_value
```

## Run a scenario

Without providing a scenario argument, only the tests without any `@scenario` decorator will be executed. We provide a scenario name to `run.sh` to run tests decorated with the given scenario.

```bash
./run.sh <SCENARIO_NAME>
# e.g, "LIBRARY_CONF_CUSTOM_HEADER_TAGS" to run the LIBRARY_CONF_CUSTOM_HEADER_TAGS scenario
```

## Run a scenario group

You can run a group of scenarios as they are defined in `scenario_groups.yml`

```bash
./run.sh <SCENARIO_GROUP_NAME>
# e.g, "APPSEC_SCENARIOS" to run most of APPSEC scenarios
```

## Spawn components, but do nothing

```bash
./run.sh <SCENARIO_NAME> --sleep

# play with the weblog, and look inside logs_<scenario_name>/interfaces/ what's happening
```
