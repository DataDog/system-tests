# System-tests documentation

This is the documentation index for system-tests. Start from the section that matches what you need, and follow the links to go deeper.

For a quick start guide, see the [main README](../README.md).

Slack: [#apm-shared-testing](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X)

---

## Understanding system-tests

Learn what system-tests is, how it works, and what the key concepts are.

- [Understanding overview](understand/README.md) -- entry point for concepts
- [Architecture overview](understand/architecture.md) -- components, containers, data flow, and what system-tests is good (and bad) at
- [Scenarios](understand/scenarios/README.md) -- the different types of tests: end-to-end, parametric, SSI, Kubernetes
- [Weblogs](understand/weblogs/README.md) -- the test applications that get instrumented by tracer libraries
- [Test flow](understand/test-flow.md) -- the full test execution flow (setup, wait, test)
- [Glossary](glossary.md) -- definitions of terms like pass, fail, xpass, xfail, enabled, disabled
- [Ownership](who-is-the-owner.md) -- who owns what in this repository

## Running tests

Everything you need to build images and execute test scenarios.

- [Execute overview](execute/README.md) -- entry point for running tests
- [Build](execute/build.md) -- build options, weblog variants, image names
- [Run](execute/run.md) -- run options, test selection, scenarios, sleep mode, timeouts
- [Test outcomes](execute/test-outcomes.md) -- understanding test result symbols and states
- [Logs](execute/logs.md) -- the log folder structure and what each file contains
- [Replay mode](execute/replay.md) -- re-run test methods without rebuilding the environment
- [Custom tracer versions](execute/binaries.md) -- testing with local or unmerged tracer builds
- [Force execute](execute/force-execute.md) -- running disabled tests on demand
- [Skip empty scenarios](execute/skip-empty-scenario.md) -- behavior when a scenario has no matching tests
- [Xfail strict mode](execute/xfail-strict.md) -- strict xfail behavior
- [Troubleshooting](execute/troubleshooting.md) -- common issues when running tests
- [Debug traces](execute/dd-trace-debug.md) -- activating tracer debug output
- [SSI execution](execute/ssi.md) -- running SSI-specific scenarios
- [End-to-end execution](execute/e2e.md) -- running end-to-end scenarios

## Writing and editing tests

How to add, modify, enable, and disable tests.

- [Edit overview](edit/README.md) -- entry point for editing tests
- [Add a new test](edit/add-new-test.md) -- step-by-step guide for creating a test
- [Add a new scenario](edit/scenarios.md) -- creating new test scenarios
- [Enable a test](edit/enable-test.md) -- activating a test for a library version
- [Skip / disable tests](edit/skip-tests.md) -- decorators for conditional test skipping
- [Manifests](edit/manifest.md) -- the YAML files that control test activation per library
- [Versions](edit/versions.md) -- version specification guidelines
- [Features](edit/features.md) -- linking tests to the feature parity dashboard
- [Formatting](edit/format.md) -- linter and code style (`format.sh`)
- [IAST validations](edit/iast-validations.md) -- marking tests with vulnerabilities
- [Remote config](edit/remote-config.md) -- writing remote config tests
- [CI and scenarios](edit/CI-and-scenarios.md) -- how scenarios are wired into CI
- [Update Docker images](edit/update-docker-images.md) -- modifying test app Docker images
- [Runbook](edit/runbook.md) -- operational runbook
- [Troubleshooting](edit/troubleshooting.md) -- debugging tips during development
- [Flushing](edit/flushing.md) -- how data flushing works and implementing `/flush`
- [Library interface validation](edit/library-interface-validation-methods.md) -- API reference for validating tracer-to-agent traces
- [Agent interface validation](edit/agent-interface-validation-methods.md) -- API reference for validating agent-to-backend data
- [Backend interface validation](edit/backend-interface-validation-methods.md) -- API reference for validating backend API responses

## Scenario-specific guides

Deep dives into each scenario type.

- **End-to-end**: covered in [scenarios overview](understand/scenarios/README.md) and [architecture](understand/architecture.md)
- **Parametric**: [overview](understand/scenarios/parametric.md) and [contributing guide](edit/parametric_contributing.md)
- **AWS SSI / Onboarding**: [full guide](understand/scenarios/onboarding.md) and [provision structure](understand/scenarios/onboarding_provision_section.md)
- **Docker SSI**: [guide](understand/scenarios/docker_ssi.md) and [Docker fixtures](understand/scenarios/docker_fixtures.md)
- **Kubernetes lib injection**: [overview](understand/scenarios/k8s_library_injection_overview.md), [details](understand/scenarios/k8s_lib_injection.md), and [injector dev](understand/scenarios/k8s_injector_dev.md)
- **Other scenarios**: [lifecycle](understand/scenarios/lifecycle.md), [IPv6](understand/scenarios/IPv6.md), [Go proxies](understand/scenarios/go_proxies_envoy_haproxy.md), [AWS Lambda](understand/scenarios/aws_lambda.md), [integration frameworks](understand/scenarios/integration_frameworks.md)

## CI integration

Adding system-tests to your continuous integration pipeline.

- [CI overview](ci/README.md) -- general steps to integrate
- [GitHub Actions](ci/github-actions.md) -- GitHub Actions workflow
- [GitLab CI](ci/gitlab-ci.md) -- GitLab CI setup
- [System-tests CI](ci/system-tests-ci.md) -- how the system-tests own CI pipeline works

## Weblogs

The test applications that tracers instrument.

- [Weblog overview](understand/weblogs/README.md) -- types of weblogs
- [End-to-end weblog spec](understand/weblogs/end-to-end_weblog.md) -- all endpoints and their expected behavior
- [GraphQL weblog](understand/weblogs/graphql_weblog.md) -- GraphQL-specific weblog

## Internals

Deep dives for maintainers and contributors to the system-tests framework itself.

- [Internals overview](internals/README.md) -- index of internal documentation
- [End-to-end lifecycle](internals/end-to-end-life-cycle.md) -- how e2e scenarios execute step by step
- [Parametric lifecycle](internals/parametric-life-cycle.md) -- how parametric scenarios execute
- [Pytest internals](internals/pytest.md) -- log levels and pytest configuration
- [Requirements](internals/requirements.md) -- internal dependency requirements
- [History](internals/history.md) -- historical context
- [MITM certificate](internals/recreating_MITM_certificate.md) -- recreating the proxy certificate
- [Protobuf files](internals/recreating_protobuf_files.md) -- regenerating protobuf definitions
- [Core dump generation](internals/generate-core-dump.md) -- generating core dumps for debugging
- [Async model revamp](internals/revamp-asynchronous-model.md) -- asynchronous model documentation
- [PR reviews](internals/PR-reviews.md) -- pull request review guidelines

## RFCs

- [RFCs](rfcs/README.md) -- historical Request for Comments documents
- [Manifest RFC](rfcs/manifest.md) -- the original manifest design proposal

## AI tooling

- [AI integration guide](ai/ai-tools-integration-guide.md) -- built-in rules for AI-assisted development
- [Cursor guide](ai/cursor-ai-comprehensive-guide.md) -- comprehensive Cursor AI guide
- [Cursor specialized prompts](ai/cursor-specialized-prompts.md) -- specialized task prompts
- [Cursor examples](ai/cursor-practical-examples.md) -- practical usage examples
- [Prompt validation](ai/ai-tools-prompt-validation.md) -- testing AI prompts with promptfoo
- [GitHub MCP server](ai/ai-github-mcp-server.md) -- GitHub MCP server integration
- [Java endpoint prompt](ai/ai-prompt-java-endpoint-prompt.md) -- Java endpoint creation prompt
