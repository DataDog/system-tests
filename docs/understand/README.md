# Understanding system-tests

This section covers the core concepts of system-tests: what the components are, how they fit together, and what types of tests exist.

## Architecture

- [Architecture overview](architecture.md) -- components, containers, data flow, and what system-tests is good (and bad) at
- [Test flow](test-flow.md) -- the full test execution flow (setup, wait, test)

## Scenarios

Scenarios define what gets tested and how. See the [scenarios overview](scenarios/README.md) for the full picture, or jump to a specific type:

- [End-to-end](scenarios/README.md#end-to-end-scenarios) -- the most common scenario type, testing the full trace lifecycle
- [Parametric](scenarios/parametric.md) -- lightweight tests for tracer/span interfaces
- [AWS SSI / Onboarding](scenarios/onboarding.md) -- auto-instrumentation on VMs
- [Docker SSI](scenarios/docker_ssi.md) -- auto-instrumentation in Docker containers
- [Kubernetes lib injection](scenarios/k8s_library_injection_overview.md) -- auto-instrumentation in K8s
- [Scenario lifecycle](scenarios/README.md#scenario-lifecycle) -- how scenarios execute step by step

## Weblogs

Weblogs are the test applications that tracers instrument. See the [weblogs overview](weblogs/README.md), or:

- [End-to-end weblog spec](weblogs/end-to-end_weblog.md) -- all endpoints and their expected behavior
- [GraphQL weblog](weblogs/graphql_weblog.md) -- GraphQL-specific weblog

## Reference

- [Glossary](../glossary.md) -- definitions of pass, fail, xpass, xfail, enabled, disabled

---

## See also

- [Running tests](../execute/README.md) -- how to build and execute scenarios
- [Writing tests](../edit/README.md) -- how to add or modify tests
- [Back to documentation index](../README.md)
