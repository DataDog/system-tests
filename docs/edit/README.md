System tests allow developers define scenarios and ensure datadog libraries produce consistent telemetry (that is, traces, metrics, profiles, etc...). This "edit" section addresses the following use-cases:

1. Adding a new test (maybe to support a new or existing feature)
2. Modifying an existing test, whether that's modifying the test client (test*.py files) or the weblog and/or parametric apps that serve the test client requests)
3. Enabling/disabling tests for libraries under various conditions

**Note: Anytime you make changes and open a PR, re-run the linter**: [format.md](docs/edit/format.md)

To make changes, you must be able to run tests locally. Instructions for running **end-to-end** tests can be found [here](https://github.com/DataDog/system-tests/blob/main/docs/execute/README.md#run-tests) and for **parametric**, [here](https://github.com/DataDog/system-tests/blob/main/docs/scenarios/parametric.md#running-the-tests).

**Callout**

You'll commonly need to run unmerged changes to your library against system tests (e.g. to ensure the feature is up to spec). Instructions for testing against unmerged changes can be found in [enable-test.md](./enable-test.md).

## Index
1. [add-new-test.md](./add-new-test.md): Add a new test
2. [scenarios.md](./scenarios.md): Add a new scenario
3. [format.md](./format.md): Use the linter
4. [features.md](./features.md): Mark tests for the feature parity dashboard
5. [enable-test.md](./enable-test.md): Enable a test
6. [skip-tests.md](./skip-tests.md): Disable tests
7. [manifest.md](./manifest.md): How tests are marked as enabled or disabled for libraries
8. [troubleshooting.md](./troubleshooting.md) Tips for debugging
9. [iast-validations.md](./iast-validations.md): Mark tests with vulnerabilities
10. [CI-and-scenarios.md](./CI-and-scenarios.md): Understand how scenarios run in CI
11. [update-docker-images.md](./update-docker-images.md): Modify test app docker images
12. [remote-config.md](./remote-config.md): Write remote config tests
