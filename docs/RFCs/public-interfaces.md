# RFC status

* Initiated : November 2026
* Validated : -
* Implemented : -

### Context

system-tests has no formal boundary between its internals (`utils/`) and the code that uses them. Anything can import anything:

- **Tests** are supposed to use `from utils import ...` and the `utils.pytest` facade, but outside `tests/test_the_test/` about 400 import lines in 209 test files reach into `utils.<submodule>` directly, private ones included (`utils._weblog`, `utils._context.containers`, `utils.docker_fixtures._test_agent`...).
- **Scenario definitions** (`utils/_context/_scenarios/*.py`) import the containers, the Docker layer, constants, ports and the logger from wherever they live.
- **Build tooling** (`build.sh`, `utils/scripts`, `utils/ci`, and external consumers such as the Nix package in `dd-trace-ops`) picks whatever internal it needs (`utils.const.COMPONENT_GROUPS`, `utils.base_images.base_image.base_image_contexts`, `utils._context.containers.dockerfile_image_list`...).
- **`context`** is both the global state scenarios write to and the object tests read from. Tests mostly use it for `context.library` (about 400 uses) and `context.weblog_variant`, but also for `context._scenarios`, `context.containers` and `context.get_container_by_dd_integration_name`.

Import-linter contracts have started to draw lines: tests only import the `utils` root (`utils-public-interface`), `utils` never imports `tests` (`utils-no-tests`), and Docker is fenced into a runtime layer (`docker-sdk-runtime-layer`, `container-layer-orchestration`). Each of them ratchets the existing violations. This RFC describes the target those contracts converge to.

### Issue

- Any refactor of `utils/` can break tests or scenarios in unrelated areas, and reviewers can't tell whether a change touches something users depend on.
- There is no list of what a test author, a scenario author or a build script is supposed to use. Newcomers and AI agents copy whatever import the neighbouring file uses, so internal usage keeps spreading.
- Mocks (proxy mocked responses, the mocked backend, remote config payloads) are spread across `utils/proxy`, `utils/mocked_backend` and `utils/interfaces`, with no single owner and no single way for tests to reach them.

### Proposition

Split the Python surface of system-tests into **seven public interfaces**, each with its own audience and an explicit list of exported names. Everything else in `utils/` is internal, and import-linter blocks consumers from importing it.

| Interface | Audience | Content |
|-----------|----------|---------|
| **Setup API** | test authors, in `setup_*` methods | actions that produce data: `weblog` requests, remote config updates, installing mocked responses, the action side of component handles |
| **Assertion API** | test authors, in `test_*` methods | checks on collected data: validators (`interfaces.*`), span and trace helpers, `ValidationError`, the query side of component handles |
| **Metadata API** | test authors, tooling | decorators (`bug`, `missing_feature`, `irrelevant`, `flaky`...), `features`, and a read-only scenario registry (`scenarios.xxx`, `scenario_groups`) |
| **Runtime info** | test and metadata APIs | the read-only view of what is running: library and version, weblog variant, scenario, component versions. Exposed as `context` |
| **Scenario API** | scenario authors | what a scenario definition needs to compose components: scenario base classes, component definitions, constants, ports |
| **Component API** | component authors (framework maintainers, teams adding a side container) | the contract for writing a component: lifecycle and an optional test handle |
| **Build API** | `build.sh`, CI, external tooling | listing components, weblogs and scenarios, resolving base images and image lists, building images |

The setup and assertion APIs together form the **test API**, exposed at the `utils` root. `utils.pytest` stays as is: it's the approved subset of pytest and is part of the test API.

#### Layering

```
tests/ ──────────▶ Test API (utils root) ──re-exports──▶ Metadata API ──▶ Runtime info
                       │       │                                              ▲
                       │       └──re-exports──▶ Runtime info                  │ written by
                       ▼                                                      │
               component test handles                                   scenario core (internal)
                       ▲                                                      │
                       │                                                      │
scenario definitions ──▶ Scenario API ──▶ components ──▶ Component API ──▶ runtime layer (Docker)
                                              ▲
build.sh, CI, tools ──▶ Build API ── builds images of ┘
```

- **Metadata API** depends on runtime info only, so decorators can evaluate conditions (`@bug(context.library < "java@1.2")`) without importing the test API.
- **Test API** re-exports the metadata API and runtime info, so test authors keep a single import root (`from utils import ...`) and the 574 existing `from utils import` lines stay valid.
- **Setup API** and **assertion API** don't import each other. Both can read runtime info.
- **Scenario API** never imports the test API. Scenario definitions import only the scenario API.
- **Runtime info** is read-only for its consumers. Only the scenario core writes to it, through an internal module.

#### Components

A component is anything a scenario starts next to the library under test: the weblog, the agent, the test agent, the proxy, the mocked backend, postgres, kafka... They all have the same shape:

- a **definition**: image, configuration, lifecycle (build, start, healthcheck, stop), logs. Scenarios use it.
- an optional **test handle**: what tests use to query what the component received, install mocked responses or assert. Postgres has none. The proxy has a rich one (`interfaces.library`, `interfaces.agent`, mocked tracer responses), and so does the mocked backend.

Mocks are components, not part of the test framework. They have the same status as a postgres container, except that they expose a test handle.

Tests never import a component directly. The test API **re-exports** the handles behind stable names (`interfaces.*` today, plus the mock helpers), so components can be reorganised without touching tests.

#### Setup and test functions

End-to-end tests run in two phases. All `setup_*` methods run first, while the scenario is up, and their results (`self.r = weblog.get(...)`) are stored. Then the scenario stops, and the `test_*` methods assert on what the components collected. With `--replay`, setup methods don't run: their stored results are restored, and the tests run against the logs of a previous run.

So the two phases need different things, and mixing them breaks something:

- an action in a `test_*` method (a weblog request, a remote config update) happens after the components stopped collecting, and doesn't happen at all in replay mode;
- an assertion in a `setup_*` method fails before the data it checks has been collected.

The test API is therefore split in two: a **setup API** for actions and an **assertion API** for checks. Component handles are split the same way. The proxy handle, for example, exposes "send these mocked responses" on the setup side and "these spans were received" on the assertion side.

The two APIs live in `utils.tests_api.setup` and `utils.tests_api.assertion`. At first the `utils` root keeps re-exporting both, so existing tests don't change. Importing from the two modules explicitly comes in a later step. Each public name should belong to exactly one phase: the more that holds, the simpler the checks below. Names that belong to neither (constants, enums, types, `context`) are neutral and usable in both.

Import-linter can't enforce this split, because both phases live in the same file. It's enforced by a static check, backed by a runtime guard.

**Static check.** A small AST checker run by `./format.sh` (ruff has no plugin system), with a ratchet file for existing violations:

- the interfaces declare the phase of each name, the checker doesn't: membership of `utils.tests_api.setup` or `utils.tests_api.assertion`, plus a decorator (`@setup_only`, `@assertion_only`) on the members of handles that serve both phases, such as `interfaces.agent.wait_for`, which waits in a setup method for data to arrive;
- for each test class, the checker classifies `setup_*` and `test_*` methods by name, resolves every name used to its import and follows attribute chains (`interfaces.agent.wait_for`) to the declared member;
- helpers defined in the same file (module functions, other methods, base classes in the file) inherit the phases of their callers. Helpers in other files are not a concern: tests can't import other tests (`no-cross-test-imports`), and helpers in `utils` are part of an API, so they are already classified.

A prototype on today's end-to-end tests (1,102 setup and 1,446 test methods) found no `weblog` call in a test method. Classifying by top-level name only (`weblog`, `remote_config` = setup; `interfaces` = assertion) gives 12 hits, all false positives (`interfaces.agent.wait_for` in setup methods, the `remote_config.ApplyState` enum in a test method). That's why phases are declared per member, not per name.

**Runtime guard.** What the checker can't see (`getattr`, handles passed around as values, lambdas) is caught when the test runs: setup API calls raise outside a setup method, and assertion API calls raise inside one.

Parametric tests (`docker_fixtures`) don't have two phases: one test function drives the library through its fixtures and asserts on the result. They use both APIs and are out of scope for the phase checks.

#### `context`

`context` is too widely used to remove. It becomes the **runtime info** interface: a read-only view of what is running, re-exported by the test API under its current name.

- Reads stay as they are (`context.library`, `context.weblog_variant`, `context.scenario`...).
- Writes move to an internal setter used only by the scenario core.
- Attributes that expose internals (`context._scenarios`, `context.containers`, `context.get_container_by_dd_integration_name`) are replaced by runtime info fields or component handles.
- Read-only is enforced at the type level (properties, frozen dataclasses) so mypy reports writes. No runtime enforcement.

#### Build API

The build process moves from shell scripts to Python. `utils.build_api` is its entry point, with a single CLI (`python -m utils.build_api <command>`) that shell scripts and external tools call instead of individual scripts. It builds the images of components (weblog, parametric app, proxy...), so its consumers are components and CI, not scenarios.

`utils.build_api` must be importable without the test runtime, which follows from the next rule.

#### Imports have no side effects

Importing any public interface, or any module behind it, only makes symbols available. It doesn't open sockets or files, start threads or processes, read or change the environment, configure logging, allocate ports or build runtime objects. Anything with an effect happens in an explicit call: scenario setup, a fixture, a CLI command.

Today `import utils` breaks this rule:

- `utils/__init__.py` creates the `weblog`, `context` and `scenarios` singletons and the `interfaces.*` validators. Creating `scenarios` builds every scenario object and, through them, their container objects.
- The four Docker SSI scenarios each bind a socket at import to pick a free agent port (`_get_free_port()` in `_DockerSSIScenario.__init__`, `utils/_context/_scenarios/docker_ssi.py`).
- Build tooling works around it: `utils/const/__main__.py` does `from _const import *` to avoid importing `utils` at all.

Singletons become lazy: module `__getattr__` (PEP 562) on the interface modules, or accessors that build the object on first use. Scenarios register a description at import and build their containers and resources only when selected and set up.

This is checked by a test that imports each interface module in a fresh interpreter under a Python audit hook (PEP 578, `sys.addaudithook`). It fails on `socket.*`, `subprocess.*`, file writes, `os.putenv`/`os.unsetenv`, `_thread.start_new_thread` and the like, and also checks that the thread count and root logging handlers are unchanged. Effects of third-party packages (urllib3 binds `::1` at import to detect IPv6) and today's own violations are allow-listed, and the allow-list only shrinks. Effects without an audit event (building a large object graph, reading `os.environ`) are left to review and to the laziness above.

Pro:

- One reviewable list per audience. Adding to an interface is an explicit decision, visible in review.
- Internals, components and the container backend can be refactored freely as long as the interfaces keep their signatures.
- Enforced in CI: `./format.sh` already runs `lint-imports`.

Cost:

- A migration of about 400 test import lines plus the scenario definitions, mostly mechanical, spread over several PRs.
- The interfaces must be maintained: a new public helper needs a re-export.

## Implementation

### Interface modules

- An interface module contains only imports, re-exports and `__all__`. No logic, and no side effect at import (see above).
- `__all__` is the contract. Names used only in annotations can be re-exported under `if TYPE_CHECKING:`, as #8676 does in `utils/__init__.py` for `TestAgentAPI`, `DataDogLibrarySpan`...
- Public submodules are kept to a minimum and listed explicitly in the contracts.

Module names are open (see below). Working names: `utils` (test API, re-exporting `utils.tests_api.setup` and `utils.tests_api.assertion`), `utils.metadata`, `utils.runtime_info`, `utils.scenario_api`, `utils.component_api`, `utils.build_api`.

### Enforcement with import-linter

Each boundary is a `protected` or `forbidden` contract with `unmatched_ignore_imports_alerting = error`. Existing violations are listed under `ignore_imports` with a `TODO` comment. The list can only shrink, and adding to it needs a justification in review.

| Boundary | Contract | Status |
|----------|----------|--------|
| tests → `utils` root only | `utils-public-interface` (protected) | merged (#8675), ratchet being reduced (#8676) |
| `utils` never imports `tests` | `utils-no-tests` (forbidden) | merged (#8678) |
| Docker only in the runtime layer | `docker-sdk-runtime-layer`, `container-layer-orchestration` | merged (#8679) |
| scenario definitions → scenario API only | protected | in review (#8681) |
| components → component API, never test or scenario APIs | forbidden | to do |
| metadata API → runtime info only | forbidden | to do |
| runtime info written only by the scenario core | protected (internal setter module) | to do |
| build tooling → build API only | protected | to do |

External consumers (the Nix package in `dd-trace-ops`) can't be enforced from this repo. The build API is documented as the only supported surface for them.

### Migration plan

Every step is shippable on its own and leaves CI green.

1. **Boundaries only.** Add the import-linter contracts above, with today's violations as ratchet ignores. No code moves. This makes the target visible and stops new violations, including new uses of `context` internals and new direct imports of components from tests. Add the import side-effect test with today's effects allow-listed.
2. **Centralise re-exports.** Create the interface modules and route consumers through them:
   - test API: re-export what tests import from internals today (helpers, types, constants, component handles and mocks), sorted into the setup and assertion APIs, then rewrite test imports with a codemod, area by area. Add the phase checks with a ratchet;
   - scenario API: re-export the targets scenario definitions use most (`_logger`, `_context.constants`, `_context.containers`, `_context.component_version`, `interfaces`, `proxy.ports`). That clears every declarative scenario definition. The infrastructure-heavy ones (docker_ssi, k8s, VM, docker_fixtures) may get a sub-API per backend;
   - runtime info: split `context` into the read-only view and the internal setter;
   - side effects: make the singletons lazy and move resource allocation (such as the Docker SSI free port) to scenario setup, shrinking the allow-list of the import test;
   - build API: create `utils.build_api` and its CLI, and move `build.sh`, `utils/scripts` and `utils/ci` onto it.

   Each move removes ratchet lines.
3. **Converge components.** Define the component API (lifecycle and test handle) and migrate components one at a time: proxy, mocked backend, agent, test agent, weblog, side containers. Move the build of their images from shell to the build API.
4. **Explicit phase imports.** Tests import from `utils.tests_api.setup` and `utils.tests_api.assertion` instead of the `utils` root (codemod), and the root re-exports of the two APIs are deprecated.
5. **Document** each interface for its audience (`docs/edit/` for tests and scenarios, `docs/internals/` for components and build), and point the AI rules (`docs/ai/`) at them.

## Open questions

- Is the runtime guard worth its cost once the static check exists, or is a ratchet on the static check enough?
- Module names and layout: flat modules under `utils/`, or root packages (`scenarios/`, `components/`) next to `tests/`?
- Should the metadata API also accept declarative conditions (`@bug(library="java@<1.2")`), so that decorators and manifests share one condition format?
- Should the parametric clients (`TestAgentAPI`, `ParametricTestClientApi`) be public types, or only reachable through fixtures?
- Should `tests/test_the_test/` keep unrestricted access to internals, or only what it needs?
