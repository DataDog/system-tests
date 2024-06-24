### End to end testing

Note there's likely a more up-to-date version in [Confluence](https://datadoghq.atlassian.net/wiki/spaces/APMINT/pages/2882407122/APM+end-to-end+E2E+tests#Fetch-Single-Span-spans/events).
Please check that for more information.

### Prerequisites

To run locally, make sure you have valid `DD_API_KEY` and `DD_APPLICATION_KEY` in your environment.
They must belong to the allow-listed [org](https://github.com/DataDog/consul-config/blob/b84d79f702961414b6d262b1190ff04bb5efd0a2/datadog/us1.prod.dog/features/event_platform_unstable_analytics_endpoint#L4).
Check this site-to-host for easier [navigation](https://github.com/DataDog/system-tests/blob/1219af3e6bdfb16c939a687ffeff2123aa41b52b/utils/interfaces/_backend.py#L35).

### Instructions

#### Instructions to run the tests

- Make sure you built the appropriate version of the weblog, for example single span sampling at the time of writing is using Go Chi.
  - To build the weblog, run `./build.sh -l golang -w <chi or net-http or etc>` from the system-tests directory.
- Run `./run.sh <scenario name >` to run the tests, for example `./run.sh APM_TRACING_E2E_SINGLE_SPAN`.

#### Instructions to add new tests or scenarii

If you are writing a new test:

- attached to the `DEFAULT` scenario (the most common one): you don't need to add anything before the test func.
- attached to a specific scenario: add `@scenarios.<scenario name>` before your test func.

If you want to create a new scenario, do it in `_scenarios.py`.
Creating a new scenario comes at a cost.
It is quite often reasonable to keep the tests in `DEFAULT` scenario.
Checkout `.github/workflows/ci.yml` if you want to add a test case in CI.
