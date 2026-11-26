### End to end testing
Note there's likely a more up-to-date version in [Confluence](https://datadoghq.atlassian.net/wiki/spaces/APMINT/pages/2882407122/APM+end-to-end+E2E+tests#Fetch-Single-Span-spans/events).
Please check that for more information.

### Prerequisites
No Datadog API or APP key is needed: end-to-end scenarios send their data to a mocked backend. Do not export
`DD_API_KEY` or `DD_APPLICATION_KEY`: in CI, the test runner fails if it finds a secret in its environment (see
[troubleshooting](./troubleshooting.md#environment-variables-look-like-secrets)).

### Instructions

#### Instructions to run the tests

* Make sure you built the appropriate version of the weblog, for example single span sampling at the time of writing is using Go Chi.
  * To build the weblog, run `./build.sh -l golang -w <chi or net-http or etc>` from the system-tests directory.
* Run `./run.sh <SCENARIO_NAME>` to run the tests, for example `./run.sh APM_TRACING_E2E_SINGLE_SPAN`.

#### Instructions to add new tests or scenarii

If you are writing a new test:
* attached to the `DEFAULT` scenario (the most common one): you don't need to add anything before the test func.
* attached to a specific scenario: add `@scenarios.<scenario name>` before your test func.

If you want to create a new scenario, do it in `_scenarios.py`.
Creating a new scenario comes at a cost.
It is quite often reasonable to keep the tests in `DEFAULT` scenario.
Checkout `.github/workflows/ci.yml` if you want to add a test case in CI.
