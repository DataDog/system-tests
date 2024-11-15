System tests allow developers define scenarios and ensure datadog libraries produce consistent telemetry (that is, traces, metrics, profiles, etc...). This "edit" section addresses the following use-cases:

1. Adding a new test (maybe to support a new or existing feature)
2. Modifying an existing test, whether that's modifying the test client (test*.py files) or the weblog and/or parametric apps that serve the test client requests)
3. Enabling/disabling tests for libraries under various conditions

To make changes, you must be able to run tests locally. Instructions for running **end-to-end** tests can be found [here](https://github.com/DataDog/system-tests/blob/main/docs/execute/README.md#run-tests) and for **parametric**, [here](https://github.com/DataDog/system-tests/blob/main/docs/scenarios/parametric.md#running-the-tests).

**Callout**

You'll commonly need to run unmerged changes to your library against system tests (e.g. to ensure the feature is up to spec). Instructions for testing against unmerged changes can be found in [enable-tests.md](./enable-tests.md).

## Index
1. [lifecycle.md](./lifecycle.md): Understand how system tests work
2. [add-test-class.md](./add-test-class.md): Add a new test
3. [scenarios.md](./scenarios.md): Add a new scenario
4. [features.md](./features.md): Mark tests for the feature parity dashboard
5. [format.md](./format.md): Use the linter
6. [manifest.md](./manifest.md): How tests are marked as enabled or disabled for libraries
7. [enable-tests.md](./enable-tests.md): Enable tests
8. [skip-tests.md](./skip-tests.md): Disable tests
9. [versions.md](./versions.md) Specify version for enabling/disabling tests
10. [remote-config.md](./remote-config.md): Understand how we test remote config
11. [troubleshooting.md](./troubleshooting.md) Tips for debugging
12. [iast-validations.md](./iast-validations.md): Mark tests with vulnerabilities
