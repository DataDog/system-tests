## What is system-tests?

Having trouble? Reach out on slack: [#apm-shared-testing](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X)

System-tests is a black-box testing workbench for Datadog tracer libraries. It runs the **same tests** against every tracer implementation -- Java, Node.js, Python, PHP, Ruby, C++, .NET, Go, and Rust -- so shared features stay consistent across languages.

Key principles:

* **Black-box testing** -- only component interfaces are checked, no assumptions about internals. "Check that the car moves, regardless of the engine."
* **Cross-language** -- one test validates all tracer libraries.

## Quick start

You need **bash**, **Docker** (20.10+), and **Python 3.12** ([installation guide](#python-312-installation)).

```bash
# 1. Set up the Python environment
./build.sh -i runner
source venv/bin/activate

# 2. Build images for the language you want to test
./build.sh python          # or: java, nodejs, ruby, php, dotnet, cpp, golang

# 3. Run the tests
./run.sh                   # run all default tests
./run.sh SCENARIO_NAME     # run a specific scenario
./run.sh tests/test_smoke.py::Test_Class::test_method   # run a single test
```

Having trouble? Check the [troubleshooting page](docs/execute/troubleshooting.md).

To understand the test output, see [test outcomes](docs/execute/test-outcomes.md) and the [glossary](docs/glossary.md).

## Documentation

All detailed documentation lives in the [`docs/`](docs/README.md) folder. Here is a guided reading order:

### Understand system-tests

| Topic | Description |
|-------|-------------|
| [Architecture overview](docs/understand/architecture.md) | Components, containers, data flow |
| [Scenarios](docs/understand/scenarios/README.md) | End-to-end, parametric, SSI, K8s -- what each one tests |
| [Weblogs](docs/understand/weblogs/README.md) | The test applications instrumented by tracers |
| [Glossary](docs/glossary.md) | Definitions of pass, fail, xpass, xfail, etc. |

### Run tests

| Topic | Description |
|-------|-------------|
| [Build](docs/execute/build.md) | Build options, weblog variants, image names |
| [Run](docs/execute/run.md) | Run options, selecting tests, scenarios, timeouts |
| [Logs](docs/execute/logs.md) | Understanding the logs folder structure |
| [Test outcomes](docs/execute/test-outcomes.md) | Reading test results |
| [Replay mode](docs/execute/replay.md) | Re-run tests without starting the containers |
| [Custom tracer versions](docs/execute/binaries.md) | Testing with local tracer builds |
| [Troubleshooting](docs/execute/troubleshooting.md) | Common issues and how to fix them |

### Write and edit tests

| Topic | Description |
|-------|-------------|
| [Add a new test](docs/edit/add-new-test.md) | Step-by-step guide to adding tests |
| [Add a new scenario](docs/edit/scenarios.md) | Creating new test scenarios |
| [Enable / disable tests](docs/edit/enable-test.md) | Activating tests for a library version |
| [Manifests](docs/edit/manifest.md) | How test activation is declared per library |
| [Skip tests](docs/edit/skip-tests.md) | Decorators for conditional skipping |
| [Features](docs/edit/features.md) | Linking tests to the feature parity dashboard |
| [Formatting](docs/edit/format.md) | Linter and code style |
| [Troubleshooting](docs/execute/troubleshooting.md) | Debugging tips for test development |

### CI integration

| Topic | Description |
|-------|-------------|
| [CI overview](docs/CI/README.md) | Adding system-tests to your CI pipeline |
| [GitHub Actions](docs/CI/github-actions.md) | GitHub Actions workflow details |
| [System-tests CI](docs/CI/system-tests-ci.md) | How the system-tests own CI works |

### Internals

| Topic | Description |
|-------|-------------|
| [Internals overview](docs/internals/README.md) | Deep-dive index for maintainers |
| [End-to-end lifecycle](docs/internals/end-to-end-life-cycle.md) | How e2e scenarios execute step by step |
| [Parametric lifecycle](docs/understand/scenarios/parametric.md#parametric-lifecycle) | How parametric scenarios execute |
| [Interface validation](docs/edit/library-interface-validation-methods.md) | API reference for validating intercepted traces |

### AI tooling

| Topic | Description |
|-------|-------------|
| [AI integration guide](docs/ai/ai-tools-integration-guide.md) | Built-in rules for AI-assisted development |

## Additional requirements

Specific scenarios may require additional tools:

- **Kubernetes tests** -- require Kind/Minikube for local K8s clusters. See [K8s docs](docs/understand/scenarios/k8s_library_injection_overview.md).
- **AWS SSI tests** -- require AWS credentials and Pulumi setup. See [AWS SSI docs](docs/understand/scenarios/onboarding.md).

## Contributing

Before submitting a PR, always run the [linter](docs/edit/format.md) (`./format.sh`). Here are the most common types of contributions, ordered by frequency:

| What you want to do | Guide |
|----------------------|-------|
| Activate or deactivate a test for a library | [Manifests](docs/edit/manifest.md), [enable a test](docs/edit/enable-test.md), [skip tests](docs/edit/skip-tests.md) |
| Add or edit a test | [Add a new test](docs/edit/add-new-test.md), [editing overview](docs/edit/README.md) |
| Add or edit a scenario | [Scenarios guide](docs/edit/scenarios.md), [scenarios overview](docs/understand/scenarios/README.md) |
| Add or edit a weblog | [Weblog spec](docs/understand/weblogs/end-to-end_weblog.md), [build options](docs/execute/build.md) |
| Other changes | [Full editing docs](docs/edit/README.md), [internals](docs/internals/README.md) |

For testing against unmerged tracer changes, see [enable-test.md](docs/edit/enable-test.md) and [binaries](docs/execute/binaries.md).

## Ownership

* Inside `/tests/`
    * Check `.github/CODEOWNERS` first.
    * The `@features(...)` decorator on a test class/method names the precise owner.
* Inside `/utils/build/docker/<lang>/`
    * Owned by the corresponding `<lang>` guild.
* Everything else
    * Owned by `@DataDog/system-tests-core`.

## Need help?

Drop a message in [#apm-shared-testing](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X) -- we're happy to help!
