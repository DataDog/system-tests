# RFC status

* Initiated : November 2026
* Validated : -
* Implemented : -

### Context

system-tests has no boundary between its internals (`utils/`) and the code that uses them:

- **Tests**: outside `tests/test_the_test/`, about 400 import lines in 209 files reach into `utils.<submodule>`, private ones included (`utils._weblog`, `utils._context.containers`...).
- **Scenario definitions** import containers, the Docker layer, constants, ports and the logger from wherever they live.
- **Build tooling** (`build.sh`, `utils/scripts`, `utils/ci`, external tools) picks internals such as `utils.const.COMPONENT_GROUPS` or `utils._context.containers.dockerfile_image_list`.
- **`context`** is both the state scenarios write and the object tests read, internals included (`context._scenarios`, `context.containers`).

Import-linter contracts have started to fence some boundaries (`utils-public-interface`, `utils-no-tests`, `docker-sdk-runtime-layer`, `container-layer-orchestration`), each with a ratchet. This RFC describes the target they converge to.

### Issue

- Any refactor of `utils/` can break unrelated tests or scenarios, and reviewers can't tell what users depend on.
- Nothing says what a test author, a scenario author or a build script should use, so newcomers and AI agents copy the neighbouring import and internal usage spreads.
- Mocks (proxy mocked responses, mocked backend, remote config) are spread across `utils/proxy`, `utils/mocked_backend` and `utils/interfaces`, with no owner and no single way to reach them.

### Proposition

Six public interfaces, each with an audience and an explicit `__all__`. Everything else in `utils/` is internal, and import-linter blocks it.

| Interface | Audience | Content |
|-----------|----------|---------|
| **Test API** | test authors | `utils.components.<component>.live` and `.record` (see below). At the `utils` root: helpers on collected data, `ValidationError`, `utils.pytest`, re-exports of the metadata API and runtime info |
| **Metadata API** | test authors, tooling | decorators (`bug`, `missing_feature`...), `features`, read-only scenario registry |
| **Runtime info** | test and metadata APIs | read-only view of what is running (library, weblog variant, scenario, component versions), exposed as `context` |
| **Scenario API** | scenario authors | scenario base classes, component definitions, constants, ports |
| **Component API** | component authors | lifecycle and optional test handle |
| **Build API** | `build.sh`, CI, external tools | listing components, weblogs and scenarios, base images, building images |

#### Layering

```
tests/ ──┬──▶ utils root ──re-exports──▶ Metadata API ──▶ Runtime info ◀── written by ──┐
         │        └──────re-exports─────────────────────────▲                           │
         ├──▶ utils.components.<component>.live ───┐                                    │
         └──▶ utils.components.<component>.record ─┤                         scenario core (internal)
                                                   ▼                                    │
                                         component test handles                         │
                                                   ▲                                    │
scenario definitions ──▶ Scenario API ──────▶ components ──▶ Component API ──▶ runtime layer (Docker)
                                                   ▲
build.sh, CI, tools ──▶ Build API ── builds images of
```

- The metadata API depends only on runtime info, so decorators evaluate conditions (`@bug(context.library < "java@1.2")`) without the test API.
- The `utils` root re-exports the metadata API and runtime info: `from utils import features, scenarios, context, bug` stays valid.
- Scenario definitions import only the scenario API, never the test API.
- Only the scenario core writes runtime info, through an internal module.

#### Components

A component is anything the test driver starts. The **target component** is the app that embeds the library under test: the weblog in end-to-end scenarios, the parametric app in parametric ones, plus the buddies (other-language weblogs used for distributed tracing). The library is not a component of its own, since nothing starts it separately. The others are the agent, the test agent, the proxy, the mocked backend, postgres, kafka... Mocks are components like any other. End-to-end and parametric tests are not two frameworks, but scenarios that start different components.

A component has:

- a **definition** (image, configuration, lifecycle, logs), used by scenarios. It lives for a whole scenario (end-to-end) or a single test (parametric fixtures);
- an optional **test handle**, that tests reach only through `utils.components.<component>`, never through the implementation.

Components keep their own vocabulary: the weblog drives user-level behaviour over HTTP, the parametric app calls the tracer API. Today the two kinds of tests share almost no helper beyond the metadata API. Handles share a shape instead:

- an action returns a result (`r = weblog.get(...)`), and helpers reading collected data take it as their selector (`get_spans(r)`);
- helpers that collect and assert in one call (`assert_waf_attack`) are welcome. Pure checks on data stay available for helper authors and one-off checks.

#### Live and record

A test handle has up to two parts, in separate modules:

- **live** (`utils.components.<component>.live`) needs the component running: requests, remote config, mocked responses, test agent queries, waiting for data;
- **record** (`utils.components.<component>.record`) only reads what the component persisted to the log folder, so it works after the component stopped and in replay mode.

Everything sits next to what uses it: mock classes and payload builders in `live`, rule ids and record-only helpers in `record`. Little is really shared between the two parts, so there is no common module for types.

| Component | Live | Record |
|-----------|------|--------|
| weblog (target) | HTTP and gRPC requests; what its library has sent so far, waits (`wait_for`) | the responses seen by the test runner; what its library sent, captured by the proxy (`interfaces.library` today); its stdout |
| agent | what it has sent so far, waits | what it sent, captured by the proxy (`interfaces.agent` today) |
| mocked backend | mocked responses, including remote config served to the agent | captured backend payloads |
| proxy | mocked responses to the library in the agent's place, including remote config on `/v0.7/config` | none: its captures are the weblog's and the agent's records |
| parametric app (target) | tracer API calls | none |
| test agent | queries and waits (`wait_for_num_traces`...), remote config | none |
| postgres | SQL statements | none |

A mock belongs to the component that performs it, a capture to the component whose output it is. So remote config sits on the proxy or on the mocked backend depending on how the scenario serves it, as authors already choose between `tracer_rc_state` and `backend_rc_state` today.

The API is organised by component, then phase, because authors know which components their scenario starts but not each component's interface. Completion goes from what they know to what they don't: `utils.components.` lists the components, then `agent.` gives `live` and `record`, then the methods. A flat module would list every method of every component. The dedicated package keeps that first list short (the `utils` root has about 40 entries) and avoids clashes with implementation packages (`utils.proxy`). The import style (`from utils.components.agent.record import get_traces`, or `agent.record.get_traces(...)`) is up to authors. Large parts are grouped by product: the weblog's record carries everything its library sends (traces, AppSec, telemetry, remote config, profiling: 39 methods on `interfaces.library` today), so it reads `weblog.record.appsec.assert_waf_attack(...)`, `weblog.record.telemetry...`. Authors know the product they test as well as the components. Data helpers, constants, enums and types shared by several components, and `context`, belong to no phase and stay at the `utils` root. Parametric tests apply the same data helpers to data fetched live.

End-to-end tests run in two phases: `setup_*` methods run while the scenario is up, then `post_setup` stops every container, then `test_*` methods run. `--replay` skips the setup and loads the same data from the log folder. So:

- `setup_*` methods use **live**. Reading the record there sees incomplete data;
- `test_*` methods use **record** only. An action there happens after the components stopped, and not at all in replay.

Parametric tests run while their containers are up and use live only, so there is nothing to check.

What a setup method keeps for its test (`self.r = ...`) is handed from `setup_x` to `test_x` on the same test instance, not shared with other tests. `SetupProperties` persists it per test item in `setup_properties.json`, and replay restores it. Besides plain JSON values computed in setup, only three types cross today: `HttpResponse`, `GrpcResponse` and `RemoteConfigStateResults`.

**Results.** These are the only things shared by the two parts, and the only content of the component root (`utils.components.weblog` for the responses, the component applying remote config for its results):

- frozen data with no behaviour: what the live action observed, plus the key that identifies it in the records (the request id the weblog sends today). Holding one in a test method can't reach a live component;
- usable as a selector by any component's record (`weblog.record.appsec.assert_waf_attack(self.r)`, `agent.record.traces.get_spans(self.r)`);
- serialized through a common protocol (`to_json`, `from_json`, key), so a component adds a result type without changing the whitelist in `_PropertiesEncoder`.

**Static check.** An AST checker run by `./format.sh`, with a ratchet. It classifies `setup_*` and `test_*` methods by name and resolves each name to its module, through the import or the attribute chain. A live name in a `test_*` method or a record name in a `setup_*` method is a violation. Helpers in the same file inherit the phase of their callers, and tests can't import each other (`no-cross-test-imports`). On today's tests (1,102 setup and 1,446 test methods), a name-level prototype found no weblog call in a test method. Its 12 hits were `wait_for` (live) and an enum (neutral), both resolved by this layout.

**Replay.** What the checker can't see (`getattr`, handles passed as values) fails in replay mode, where tests only have the record. Running some scenarios in replay mode in CI replaces a runtime guard (`utils/scripts/replay_scenarios.sh` exists, CI doesn't run it).

The appendix shows the API in use on today's tests, including cases it fits less well.

#### `context`

`context` becomes runtime info, re-exported by the root under its current name. Reads stay as they are. Writes go through an internal setter used only by the scenario core. Attributes exposing internals (`context._scenarios`, `context.containers`, `context.get_container_by_dd_integration_name`) are replaced by runtime info fields (including component configuration, see the appendix) or component handles. Read-only is enforced by types (properties, frozen dataclasses), not at runtime.

#### Build API

The build moves from shell to Python. `utils.build_api` has a single CLI (`python -m utils.build_api <command>`) that shell scripts and external tools call. It builds component images, so its consumers are components and CI, not scenarios. It must be importable without the test runtime.

#### Imports have no side effects

Importing a public interface, or anything behind it, only makes symbols available: no sockets, files, threads, processes, environment changes, logging setup, port allocation or runtime objects. Effects happen in explicit calls: scenario setup, fixtures, CLI commands.

Today `import utils` builds the `weblog`, `context` and `scenarios` singletons, and through `scenarios` every scenario and container object. The Docker SSI scenarios bind a socket at import (`_get_free_port()` in `docker_ssi.py`), and `utils/const/__main__.py` avoids importing `utils` altogether.

Singletons become lazy (PEP 562 module `__getattr__`, or accessors), and scenarios build their resources only when selected. A test imports each interface in a fresh interpreter under an audit hook (PEP 578) and fails on sockets, subprocesses, file writes, environment changes, new threads or logging handlers. Third-party effects and today's violations are allow-listed, and the list only shrinks.

**Pro:** one reviewable list per audience; internals, components and the container backend can be refactored freely; enforced in CI by `./format.sh`.

**Cost:** a mostly mechanical migration of about 400 test import lines and the scenario definitions, over several PRs; every new public helper needs a re-export.

## Implementation

### Interface modules

An interface module contains only imports, re-exports and `__all__`. Names used only in annotations are re-exported under `if TYPE_CHECKING:`, as #8676 does in `utils/__init__.py`.

Working names (open, see below): `utils.components.<component>.live` and `.record`, `utils` (root re-exports), `utils.metadata`, `utils.runtime_info`, `utils.scenario_api`, `utils.component_api`, `utils.build_api`.

### Enforcement with import-linter

Each boundary is a `protected` or `forbidden` contract with `unmatched_ignore_imports_alerting = error`. Existing violations are `ignore_imports` with a `TODO`, and the list only shrinks. External tools can't be enforced from this repo, so the build API is documented as their only supported surface.

| Boundary | Contract | Status |
|----------|----------|--------|
| tests → `utils` root and `utils.components.*` only | `utils-public-interface` (protected) | merged for the root (#8675), ratchet being reduced (#8676) |
| `utils` never imports `tests` | `utils-no-tests` (forbidden) | merged (#8678) |
| Docker only in the runtime layer | `docker-sdk-runtime-layer`, `container-layer-orchestration` | merged (#8679) |
| scenario definitions → scenario API only | protected | in review (#8681) |
| components → component API, never test or scenario APIs | forbidden | to do |
| metadata API → runtime info only | forbidden | to do |
| runtime info written only by the scenario core | protected (internal setter module) | to do |
| build tooling → build API only | protected | to do |

### Migration plan

Every step ships on its own and leaves CI green.

1. **Boundaries only.** Add the contracts above with today's violations as ratchets, and the import side-effect test with today's effects allow-listed. No code moves.
2. **Centralise re-exports**, each move removing ratchet lines:
   - test API: create the component modules and split today's handles between them (weblog requests to `weblog.live`; mocked responses to `proxy.live` and `mocked_backend.live`, remote config to whichever of the two serves it (`tracer_rc_state` and `backend_rc_state` today); `wait_for` to `weblog.live` and `agent.live`; `interfaces.*` queries to the record parts). Rewrite test imports with a codemod, area by area. `from utils import weblog, interfaces` stays valid for existing tests only, with a ratchet. Add the static check and run some scenarios in replay mode in CI;
   - scenario API: re-export what definitions use most (`_logger`, `_context.constants`, `_context.containers`, `_context.component_version`, `interfaces`, `proxy.ports`). The infrastructure-heavy definitions (docker_ssi, k8s, VM, docker_fixtures) may get a sub-API per backend;
   - runtime info: split `context` into the read-only view and the internal setter;
   - side effects: make singletons lazy and move resource allocation to scenario setup;
   - build API: create `utils.build_api` and move `build.sh`, `utils/scripts` and `utils/ci` onto it.
3. **Converge components** on the component API (lifecycle for a scenario or a single test, test handle with live and record parts), one at a time: proxy, mocked backend, agent, test agent, weblog, parametric app, side containers. Move their image builds to the build API.
4. **Drop the root re-exports of handles** once their ratchet is empty.
5. **Document** each interface for its audience (`docs/edit/`, `docs/internals/`) and point the AI rules (`docs/ai/`) at them.

## Open questions

- Which scenarios should run in replay mode in CI, and is that enough without a runtime guard?
- Should the weblog's record hold the requests and responses seen by the test runner, so that live actions return only a reference and tests read everything from the record (`weblog.record.response(self.r).status_code`)? Only a key would cross the boundary, at the cost of more verbose reads. Tests that only use results as selectors wouldn't change.
- Module names and layout: modules under `utils/`, or root packages (`scenarios/`, `components/`) next to `tests/`?
- Should the metadata API also accept declarative conditions (`@bug(library="java@<1.2")`), so that decorators and manifests share one format?
- Should the parametric clients (`TestAgentAPI`, `ParametricTestClientApi`) be public types, or only reachable through fixtures?
- In parametric tests, what the library sent is read from the test agent. Should the parametric app's live part expose it instead (backed by the test agent), mirroring `weblog.live`?
- Should `tests/test_the_test/` keep unrestricted access to internals?

## Appendix: examples

The names below are illustrative.

**Everyday case: a request, then an assertion.** Most end-to-end tests look like this, and the change is just the import:

```python
# today
from utils import weblog, interfaces

    def setup_main(self):
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_main(self):
        interfaces.library.assert_waf_attack(self.r, rule="ua0-600-12x")

# proposed
from utils.components import weblog

    def setup_main(self):
        self.r = weblog.live.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_main(self):
        weblog.record.appsec.assert_waf_attack(self.r, rule="ua0-600-12x")
```

**Mocked agent responses** (`tests/test_sampling_rules_agent_rate.py`). Today the test imports an internal module of the proxy. The code stays the same, only the access path changes: the proxy is the component that answers the library in the agent's place, so the mocks go through its live handle, next to their types:

```python
# today
from utils.proxy.mocked_response import SequentialJsonMockedTracerResponse, send_mocked_tracer_responses

        mocked_json = {"rate_by_service": {"service:,env:": AGENT_RATE}}
        send_mocked_tracer_responses([
            SequentialJsonMockedTracerResponse(path="/v0.4/traces", mocked_json_sequence=[mocked_json]),
            SequentialJsonMockedTracerResponse(path="/v0.5/traces", mocked_json_sequence=[mocked_json]),
            SequentialJsonMockedTracerResponse(path="/v1.0/traces", mocked_json_sequence=[mocked_json]),
        ])

# proposed
from utils.components.proxy import live as proxy
from utils.components.proxy.live import SequentialJsonMockedTracerResponse

        mocked_json = {"rate_by_service": {"service:,env:": AGENT_RATE}}
        proxy.send_mocked_responses([
            SequentialJsonMockedTracerResponse(path="/v0.4/traces", mocked_json_sequence=[mocked_json]),
            SequentialJsonMockedTracerResponse(path="/v0.5/traces", mocked_json_sequence=[mocked_json]),
            SequentialJsonMockedTracerResponse(path="/v1.0/traces", mocked_json_sequence=[mocked_json]),
        ])
```

**Driving a side container** (`tests/otel_postgres_metrics_e2e/test_postgres_metrics.py`). Today the test casts the scenario to reach the container object, then shells into it:

```python
# today
        scenario: OtelCollectorScenario = context.scenario  # type: ignore[assignment]
        container = scenario.postgres_container
        container.exec_run('psql -U system_tests_user -d system_tests_dbname -c "SELECT 1;"')

# proposed: postgres gets a live handle
from utils.components import postgres

        postgres.live.execute("SELECT 1;")
```

**Interleaved actions and checks in parametric tests** (`tests/parametric/test_dynamic_configuration.py`). These tests act, observe, then act again depending on what they saw. Everything is live, fixtures return the live handles, and nothing changes but the types:

```python
    def test_rc_overrides_env(self, test_agent, test_library):
        trace = get_sampled_trace(test_library, test_agent, name="env_name")
        assert_sampling_rate(trace, ENV_SAMPLING_RULE_RATE)
        set_and_wait_rc(test_agent, test_library, config_overrides={...})
        trace = get_sampled_trace(test_library, test_agent, name="env_name")
        assert_sampling_rate(trace, RC_SAMPLING_RULE_RATE)
```

**Less well fitted: reading collected data during setup.** The same test (`test_sampling_rules_agent_rate.py`) sends bursts of requests until a span carries the mocked rate, because the rate only reaches the tracer in the response to a flush. Its setup reads collected spans, which is record data, to decide whether to act again:

```python
# today
        def has_agent_rate(_data) -> bool:
            for _, span in interfaces.library.get_root_spans():
                if abs(span.get("metrics", {}).get("_dd.agent_psr", -1) - AGENT_RATE) < 0.01:
                    return True
            return False

        for _ in range(5):
            if interfaces.library.wait_for(has_agent_rate, timeout=0):
                break
            for _ in range(20):
                weblog.get(f"/sample_rate_route/{request_idx}")
            time.sleep(2)
```

The record can't be used here, since the data isn't complete. The live part needs its own access to what was collected so far: `wait_for` and polling pass it to the predicate, and the predicate is a neutral data helper, shared with the test method:

```python
# proposed
def has_agent_rate(spans) -> bool:  # neutral: works on live or recorded data
    return any(abs(s.metrics.get("_dd.agent_psr", -1) - AGENT_RATE) < 0.01 for s in spans)

    def setup_main(self):
        for _ in range(5):
            if weblog.live.traces.poll_root_spans(has_agent_rate):
                break
            ...

    def test_main(self):
        assert has_agent_rate(weblog.record.traces.get_root_spans())
```

`tests/test_config_consistency.py` does the same on a smaller scale: a helper filters runtime metrics, and it's used both in a `wait_for` during setup and in the test method. So the live parts of components that capture data expose it, the same data the record holds later. The split is still clear at the call site, but some methods exist on both sides.

**Less well fitted: component configuration** (`tests/integrations/test_db_integrations_sql.py`). The test methods compare span tags to the credentials of the database container:

```python
# today
    def test_db_user(self):
        db_container = context.get_container_by_dd_integration_name(self.db_service)
        for _, span_meta in self.get_spans_meta():
            assert span_meta["db.user"].casefold() == db_container.db_user.casefold()
```

The database user is neither live nor record: it's configuration, fixed before the container starts and valid in both phases and in replay. It belongs to runtime info, like the library version: `context.components[self.db_service].db_user`.
