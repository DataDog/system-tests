# Parametric Test-Agent Reuse (POC) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut parametric-scenario container churn by reusing one test-agent (and one Docker network) per xdist worker, resetting agent state with a synchronous `/test/session/clear` between tests, instead of creating a fresh network + test-agent per test.

**Architecture:** Today each parametric test creates a fresh Docker bridge network, a fresh `ddapm-test-agent` container, and a fresh library-client container, then tears them all down (`utils/_context/_scenarios/_docker_fixtures.py:56-98`). This POC introduces a per-worker `WorkerAgentPool` that lazily creates one network + one test-agent per `(worker, agent_env)` key, reuses them across tests, and calls `clear()` before each test. The library client is unchanged — it already derives both its network (`test_agent.network`) and agent URL (`DD_TRACE_AGENT_URL=http://{test_agent.container_name}:8126`) from the `test_agent` object it is handed (`utils/docker_fixtures/_test_clients/_test_client_parametric.py:55,90`), so a pooled agent is transparent to it. Snapshot-marked tests fall back to the existing fresh-per-test path.

**Tech Stack:** Python 3.12, pytest + pytest-xdist, docker-py (`utils/docker_fixtures/_core.py`), the `ghcr.io/datadog/dd-apm-test-agent` image.

## Global Constraints

- **Cross-tracer blast radius:** this code is shared by all 9 tracers' parametric suites. Behavior for non-pooled paths must be byte-for-byte unchanged. Verbatim rule: do not alter `get_test_agent_api`'s existing fresh-path semantics — only add a parallel pooled path.
- **No state leakage:** a reused agent MUST start each test with no data from a prior test. The reset is `TestAgentAPI.clear()` (`utils/docker_fixtures/_test_agent.py:375-377`), called before the test runs.
- **POC scope (explicit):** pool only when the test has **no `snapshot` mark**. Snapshot-marked tests use the existing fresh path. Pool entries are keyed by the full `agent_env` dict, so tests with differing `agent_env` get separate pooled agents.
- **xdist semantics:** a pytest `scope="session"` fixture runs once **per worker** under `pytest-xdist`. That is the mechanism for "one agent per worker."
- **Default config preserved:** `agent_env` defaults to `{}` (`tests/parametric/conftest.py:38`); the vast majority of parametric tests use it, so a single pooled agent per worker covers them.
- Frequent commits: one per task minimum.

---

### Task 1: `WorkerAgentPool` + `AgentLease` (pure cache logic, no Docker)

The reuse/keying/reset logic, isolated from Docker so it is unit-testable with a fake creator.

**Files:**
- Create: `utils/docker_fixtures/_test_agent_pool.py`
- Test: `tests/test_the_test/test_test_agent_pool.py`

**Interfaces:**
- Consumes: nothing (pure logic). Creator and agent objects are injected.
- Produces:
  - `agent_env_key(agent_env: dict[str, str]) -> tuple` — stable, hashable key for an env dict.
  - `class AgentLease` with attributes `api`, `stop` (a zero-arg callable that tears the lease down).
  - `class WorkerAgentPool(creator: Callable[[dict[str, str]], AgentLease])` with:
    - `acquire(request, agent_env: dict[str, str]) -> Any` — returns the lease's `api`, creating on miss and calling `api.clear()` + `api.rebind_request(request)` on hit.
    - `shutdown() -> None` — calls every lease's `stop()` and empties the cache.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_the_test/test_test_agent_pool.py
from utils.docker_fixtures._test_agent_pool import WorkerAgentPool, agent_env_key


class _FakeApi:
    def __init__(self) -> None:
        self.clear_calls = 0
        self.rebind_calls: list[object] = []

    def clear(self) -> None:
        self.clear_calls += 1

    def rebind_request(self, request: object) -> None:
        self.rebind_calls.append(request)


class _FakeCreator:
    """Records every creation and hands back a lease whose stop() is tracked."""

    def __init__(self) -> None:
        self.created_envs: list[dict] = []
        self.stopped = 0

    def __call__(self, agent_env: dict[str, str]):
        from utils.docker_fixtures._test_agent_pool import AgentLease

        self.created_envs.append(dict(agent_env))
        api = _FakeApi()

        def _stop() -> None:
            self.stopped += 1

        return AgentLease(api=api, stop=_stop)


def test_env_key_is_order_independent():
    assert agent_env_key({"A": "1", "B": "2"}) == agent_env_key({"B": "2", "A": "1"})


def test_same_env_reuses_and_clears():
    creator = _FakeCreator()
    pool = WorkerAgentPool(creator)

    api1 = pool.acquire(request="req1", agent_env={})
    api2 = pool.acquire(request="req2", agent_env={})

    assert api1 is api2  # reused, not recreated
    assert len(creator.created_envs) == 1  # created exactly once
    assert api1.clear_calls == 1  # cleared on the reuse, not the first acquire
    assert api1.rebind_calls == ["req2"]  # rebound to the second test's request


def test_distinct_env_creates_separate_agents():
    creator = _FakeCreator()
    pool = WorkerAgentPool(creator)

    a = pool.acquire(request="r", agent_env={})
    b = pool.acquire(request="r", agent_env={"DD_ENV": "prod"})

    assert a is not b
    assert len(creator.created_envs) == 2


def test_shutdown_stops_every_lease():
    creator = _FakeCreator()
    pool = WorkerAgentPool(creator)
    pool.acquire(request="r", agent_env={})
    pool.acquire(request="r", agent_env={"DD_ENV": "prod"})

    pool.shutdown()

    assert creator.stopped == 2
    # After shutdown the cache is empty: acquiring again creates anew.
    pool.acquire(request="r", agent_env={})
    assert len(creator.created_envs) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_the_test/test_test_agent_pool.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.docker_fixtures._test_agent_pool'`

- [ ] **Step 3: Write minimal implementation**

```python
# utils/docker_fixtures/_test_agent_pool.py
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


def agent_env_key(agent_env: dict[str, str]) -> tuple:
    """Stable, hashable, order-independent key for an agent_env dict."""
    return tuple(sorted(agent_env.items()))


@dataclass
class AgentLease:
    """One running test-agent (+ its network) owned by the pool.

    `api` is a TestAgentAPI (duck-typed here so this module stays Docker-free).
    `stop` tears the lease down (container + network); it must be idempotent-safe
    to call exactly once at shutdown.
    """

    api: Any
    stop: Callable[[], None]


class WorkerAgentPool:
    """Per-worker cache of test-agents keyed by agent_env.

    First request for a given env creates a lease via `creator`; later requests
    for the same env reuse it after `api.clear()` (reset state) and
    `api.rebind_request()` (re-point per-test logging at the current test).
    """

    def __init__(self, creator: Callable[[dict[str, str]], AgentLease]) -> None:
        self._creator = creator
        self._leases: dict[tuple, AgentLease] = {}

    def acquire(self, request: Any, agent_env: dict[str, str]) -> Any:
        key = agent_env_key(agent_env)
        lease = self._leases.get(key)
        if lease is None:
            lease = self._creator(agent_env)
            self._leases[key] = lease
        else:
            lease.api.clear()
            lease.api.rebind_request(request)
        return lease.api

    def shutdown(self) -> None:
        for lease in self._leases.values():
            lease.stop()
        self._leases.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_the_test/test_test_agent_pool.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add utils/docker_fixtures/_test_agent_pool.py tests/test_the_test/test_test_agent_pool.py
git commit -m "feat(parametric): add WorkerAgentPool for test-agent reuse"
```

---

### Task 2: Extract `start_agent`/`stop_agent` + add `rebind_request`

Refactor `TestAgentFactory.get_test_agent_api` so its container-create-and-wait body is reusable by the pool without forcing per-test teardown, and give `TestAgentAPI` a way to re-point its per-test log at the current test on reuse.

**Files:**
- Modify: `utils/docker_fixtures/_test_agent.py` (factory `49-166`, `TestAgentAPI` `168-196`)

**Interfaces:**
- Consumes: `docker_run`, `get_host_port` (`utils/docker_fixtures/_core.py`); `TestAgentAPI` (this file).
- Produces:
  - `TestAgentAPI.rebind_request(self, request: pytest.FixtureRequest) -> None` — updates `self._pytest_request` and `self.log_path` to the given test.
  - `TestAgentFactory.start_agent(self, *, request, worker_id, container_name, docker_network, agent_env, container_otlp_http_port, container_otlp_grpc_port) -> tuple[TestAgentAPI, Callable[[], None]]` — runs the container, waits until ready, returns the API plus a `stop()` callable that closes the log file and stops the container. Does **not** apply snapshot marks (the pooled path never carries them).

- [ ] **Step 1: Write the failing test (Docker-backed smoke)**

```python
# tests/test_the_test/test_start_stop_agent.py
import pytest

pytestmark = pytest.mark.skipif(
    __import__("os").getenv("DOCKER_SMOKE") != "1",
    reason="Docker-backed; run with DOCKER_SMOKE=1",
)


def test_start_agent_then_stop(request):
    from utils._context._scenarios import scenarios

    factory = scenarios.parametric._test_agent_factory
    factory.configure("logs_parametric")
    factory.pull()

    network = __import__("utils.docker_fixtures._core", fromlist=["get_docker_client"])
    client = network.get_docker_client().networks.create(name="reuse_smoke_net", driver="bridge")
    try:
        api, stop = factory.start_agent(
            request=request,
            worker_id="gw0",
            container_name="ddapm-test-agent-reuse-smoke",
            docker_network=client.name,
            agent_env={},
            container_otlp_http_port=4318,
            container_otlp_grpc_port=4317,
        )
        try:
            assert api.info()["version"] == "test"  # agent answered → it is ready
        finally:
            stop()
    finally:
        client.remove()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DOCKER_SMOKE=1 python -m pytest tests/test_the_test/test_start_stop_agent.py -v`
Expected: FAIL — `AttributeError: 'TestAgentFactory' object has no attribute 'start_agent'`

- [ ] **Step 3: Add `rebind_request` to `TestAgentAPI`**

Insert this method into `TestAgentAPI` immediately after `__init__` (after `utils/docker_fixtures/_test_agent.py:196`):

```python
    def rebind_request(self, pytest_request: "pytest.FixtureRequest") -> None:
        """Re-point per-test API logging at the current test (used on reuse)."""
        self._pytest_request = pytest_request
        self.log_path = (
            f"{self._host_log_folder}/outputs/{pytest_request.cls.__name__}"
            f"/{pytest_request.node.name}/agent_api.log"
        )
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)
```

For `rebind_request` to work, `__init__` must remember `host_log_folder`. Add this line in `TestAgentAPI.__init__`, right after `self.network = network` (`utils/docker_fixtures/_test_agent.py:185`):

```python
        self._host_log_folder = host_log_folder
```

- [ ] **Step 4: Add `start_agent`/`stop_agent` to `TestAgentFactory`**

Add these methods to `TestAgentFactory` (after `pull`, before `get_test_agent_api`, around `utils/docker_fixtures/_test_agent.py:71`). This is the existing container-run-and-wait body lifted out of the context manager, returning an explicit `stop` callable instead of relying on `with`:

```python
    def start_agent(
        self,
        *,
        request: pytest.FixtureRequest,
        worker_id: str,
        container_name: str,
        docker_network: str,
        agent_env: dict[str, str],
        container_otlp_http_port: int,
        container_otlp_grpc_port: int,
    ) -> "tuple[TestAgentAPI, Callable[[], None]]":
        env = {
            "ENABLED_CHECKS": "trace_count_header",
            "OTLP_HTTP_PORT": str(container_otlp_http_port),
            "OTLP_GRPC_PORT": str(container_otlp_grpc_port),
            "VCR_CASSETTES_DIRECTORY": "/vcr-cassettes",
        }
        if os.getenv("DEV_MODE") is not None:
            env["SNAPSHOT_CI"] = "0"
        env |= agent_env

        host_port = get_host_port(worker_id, 4600)
        otlp_http_host_port = get_host_port(worker_id, 4701)
        otlp_grpc_host_port = get_host_port(worker_id, 4802)

        log_path = f"{self.host_log_folder}/outputs/{request.cls.__name__}/{request.node.name}/agent_log.log"
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, "w+", encoding="utf-8")  # noqa: SIM115

        cm = docker_run(
            image=self.image,
            name=container_name,
            env=env,
            volumes={
                "./snapshots": "/snapshots",
                "./tests/integration_frameworks/utils/vcr-cassettes": "/vcr-cassettes",
            },
            ports={
                f"8126/tcp": host_port,
                f"{container_otlp_http_port}/tcp": otlp_http_host_port,
                f"{container_otlp_grpc_port}/tcp": otlp_grpc_host_port,
            },
            log_file=log_file,
            network=docker_network,
        )
        cm.__enter__()

        client = TestAgentAPI(
            container_name,
            8126,
            self.host_log_folder,
            pytest_request=request,
            otlp_http_host_port=otlp_http_host_port,
            host_port=host_port,
            network=docker_network,
        )
        time.sleep(0.2)  # the trace agent takes ~200ms to start
        expected_version = agent_env.get("TEST_AGENT_VERSION", "test")
        for _ in range(100):
            try:
                resp = client.info()
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Wait for 0.1s for the test agent to be ready {e}")
                time.sleep(0.1)
            else:
                if resp["version"] != expected_version:
                    pytest.fail(
                        f"Agent version {resp['version']} is running instead of the test agent.",
                        pytrace=False,
                    )
                logger.info("Test agent is ready")
                break
        else:
            log_file.close()
            pytest.fail(f"Could not connect to test agent, check the log file {log_path}.", pytrace=False)

        def _stop() -> None:
            try:
                cm.__exit__(None, None, None)
            finally:
                log_file.close()

        return client, _stop
```

Add the `Callable` import at the top of the file (after `utils/docker_fixtures/_test_agent.py:2`):

```python
from collections.abc import Generator, Callable
```

(The file already imports `Generator` on line 2 — replace that single import line with the line above.)

- [ ] **Step 5: Run test to verify it passes**

Run: `DOCKER_SMOKE=1 python -m pytest tests/test_the_test/test_start_stop_agent.py -v`
Expected: PASS (1 passed). The agent container starts, `info()` returns `version == "test"`, then stops cleanly.

- [ ] **Step 6: Verify the fresh path still works (no regression)**

Run: `TEST_LIBRARY=php ./run.sh PARAMETRIC tests/parametric/test_otel_span_methods.py -k test_otel_get_span_context`
Expected: `1 passed`. (Confirms the refactor didn't break the existing per-test path, which still uses `get_test_agent_api`.)

- [ ] **Step 7: Commit**

```bash
git add utils/docker_fixtures/_test_agent.py tests/test_the_test/test_start_stop_agent.py
git commit -m "refactor(parametric): extract start_agent/stop_agent + rebind_request"
```

---

### Task 3: Worker-scoped network + pooled-agent creator on the scenario

Give the scenario a `WorkerAgentPool` whose creator builds a worker-stable network + a `start_agent` lease. The network name is keyed by worker + env so two distinct envs on one worker get distinct networks.

**Files:**
- Modify: `utils/_context/_scenarios/_docker_fixtures.py` (`34`, `56-98`)

**Interfaces:**
- Consumes: `WorkerAgentPool`, `AgentLease`, `agent_env_key` (Task 1); `TestAgentFactory.start_agent` (Task 2); `get_docker_client` (`utils/docker_fixtures/_core.py`).
- Produces:
  - `DockerFixturesScenario.get_agent_pool(self, worker_id: str) -> WorkerAgentPool` — lazily builds (once per process) a pool whose creator makes `f"{_NETWORK_PREFIX}_worker_{worker_id}_{abs(hash(key))}"` network + a `start_agent` lease named `f"ddapm-test-agent-worker-{worker_id}"`.

- [ ] **Step 1: Add pool construction to the scenario**

Add to `DockerFixturesScenario.__init__`, right after `self._test_agent_factory = TestAgentFactory(agent_image)` (`utils/_context/_scenarios/_docker_fixtures.py:34`):

```python
        self._agent_pool: "WorkerAgentPool | None" = None
```

Add these imports at the top of `utils/_context/_scenarios/_docker_fixtures.py` (with the other `from ...` lines):

```python
from utils.docker_fixtures._test_agent_pool import WorkerAgentPool, AgentLease, agent_env_key
```

Add this method to `DockerFixturesScenario` (after `_get_docker_network`, around `_docker_fixtures.py:74`):

```python
    def get_agent_pool(self, worker_id: str) -> WorkerAgentPool:
        if self._agent_pool is None:

            def _creator(agent_env: dict[str, str]) -> AgentLease:
                key = agent_env_key(agent_env)
                network_name = f"{_NETWORK_PREFIX}_worker_{worker_id}_{abs(hash(key))}"
                network = get_docker_client().networks.create(name=network_name, driver="bridge")
                container_name = f"ddapm-test-agent-worker-{worker_id}-{abs(hash(key))}"
                api, stop_agent = self._test_agent_factory.start_agent(
                    request=self._pool_seed_request,
                    worker_id=worker_id,
                    container_name=container_name,
                    docker_network=network.name,
                    agent_env=agent_env,
                    container_otlp_http_port=4318,
                    container_otlp_grpc_port=4317,
                )

                def _stop() -> None:
                    try:
                        stop_agent()
                    finally:
                        try:
                            network.remove()
                        except Exception as e:  # noqa: BLE001
                            logger.info(f"Failed to remove worker network, ignoring: {e}")

                return AgentLease(api=api, stop=_stop)

            self._agent_pool = WorkerAgentPool(_creator)
        return self._agent_pool
```

`start_agent` needs a `request` for the first-test log path. The pooled agent's container log spans the whole worker, so seed it with the first test's request and let `rebind_request` re-point the per-test API log thereafter. Add an attribute set by the fixture before first acquire — declare it in `__init__` after the `_agent_pool` line:

```python
        self._pool_seed_request = None
```

- [ ] **Step 2: Verify it imports and the fresh path is untouched**

Run: `python -c "from utils._context._scenarios import scenarios; print(type(scenarios.parametric).__mro__[1].__name__)"`
Expected: prints `DockerFixturesScenario` with no import error.

Run: `TEST_LIBRARY=php ./run.sh PARAMETRIC tests/parametric/test_otel_span_methods.py -k test_otel_get_span_context`
Expected: `1 passed` (fresh path still default — nothing calls the pool yet).

- [ ] **Step 3: Commit**

```bash
git add utils/_context/_scenarios/_docker_fixtures.py
git commit -m "feat(parametric): pooled-agent creator (worker-scoped network + agent)"
```

---

### Task 4: Wire the pool into the `test_agent` fixture (with snapshot fallback)

Make `test_agent` use the pool for non-snapshot tests and tear the pool down once per worker at session end.

**Files:**
- Modify: `tests/parametric/conftest.py` (`76-93`)

**Interfaces:**
- Consumes: `scenarios.parametric.get_agent_pool` (Task 3); `WorkerAgentPool.acquire/shutdown` (Task 1).
- Produces: a session-scoped `test_agent_pool` fixture and a pool-aware `test_agent` fixture.

- [ ] **Step 1: Add a session-scoped pool-lifecycle fixture**

Add to `tests/parametric/conftest.py` (near the other fixtures, after `agent_env`):

```python
@pytest.fixture(scope="session")
def test_agent_pool(worker_id: str):
    # scope="session" under pytest-xdist == once per worker.
    pool = scenarios.parametric.get_agent_pool(worker_id)
    yield pool
    pool.shutdown()
```

- [ ] **Step 2: Replace the `test_agent` fixture body with the pooled-or-fresh decision**

Replace the existing `test_agent` fixture (`tests/parametric/conftest.py:76-93`) with:

```python
@pytest.fixture
def test_agent(
    worker_id: str,
    test_id: str,
    request: pytest.FixtureRequest,
    agent_env: dict[str, str],
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
    test_agent_pool,
) -> Generator[TestAgentAPI, None, None]:
    # POC: pool everything except snapshot-marked tests (which need per-test
    # snapshot_context lifecycle). Pooled agents are reset with clear() between tests.
    is_snapshot = request.node.get_closest_marker("snapshot") is not None
    if not is_snapshot:
        scenarios.parametric._pool_seed_request = request
        api = test_agent_pool.acquire(request=request, agent_env=agent_env)
        api.clear()  # ensure a clean slate even on the very first acquire
        yield api
        return

    with scenarios.parametric.get_test_agent_api(
        request=request,
        worker_id=worker_id,
        test_id=test_id,
        agent_env=agent_env,
        container_otlp_http_port=test_agent_otlp_http_port,
        container_otlp_grpc_port=test_agent_otlp_grpc_port,
    ) as result:
        yield result
```

- [ ] **Step 3: Run the otel file — every test must pass through the pooled path**

Run: `TEST_LIBRARY=php ./run.sh PARAMETRIC tests/parametric/test_otel_span_methods.py`
Expected: same pass/skip/xfail counts as a baseline `git stash` run of the same command (e.g. `57 passed, 2 skipped, 2 xfailed`). No new failures.

- [ ] **Step 4: Commit**

```bash
git add tests/parametric/conftest.py
git commit -m "feat(parametric): use WorkerAgentPool in test_agent fixture"
```

---

### Task 5: Acceptance — prove reuse happened and no state leaked

Two things must be true: (a) the agent container was created roughly once per worker, not once per test; (b) results are unchanged (no cross-test leakage).

**Files:**
- Modify: `utils/docker_fixtures/_test_agent.py` (add a one-line creation counter log in `start_agent`)

**Interfaces:**
- Consumes: `start_agent` (Task 2).
- Produces: a greppable `REUSE-POC agent container created` log line per real container creation.

- [ ] **Step 1: Add a creation-count log line**

In `start_agent` (Task 2), immediately after `log_file = open(...)`, add:

```python
        logger.stdout(f"REUSE-POC agent container created: {container_name}")
```

- [ ] **Step 2: Run the otel file single-worker and count creations**

Run:
```bash
TEST_LIBRARY=php ./run.sh PARAMETRIC tests/parametric/test_otel_span_methods.py -p no:randomly -n 1 2>&1 | tee /tmp/reuse_run.log
grep -c "REUSE-POC agent container created" /tmp/reuse_run.log
```
Expected: the count equals the number of **distinct `agent_env` values** in that file (1 for the default-env otel tests), **not** the ~57 test count. Pre-change this line does not exist; the equivalent (fresh) run creates one agent per test.

- [ ] **Step 3: Leakage check — trace counts stay correct under reuse**

`test_otel_get_span_context` and `test_otel_span_operation_name` each assert exactly one trace is present. If `clear()` were incomplete, a reused agent would carry the previous test's trace and these would see 2.

Run: `TEST_LIBRARY=php ./run.sh PARAMETRIC tests/parametric/test_otel_span_methods.py -k "operation_name or get_span_context"`
Expected: all selected tests pass (each sees exactly its own single trace — proof the inter-test `clear()` reset the agent).

- [ ] **Step 4: Full-file stability (run 3×, must be green each time)**

Run:
```bash
for i in 1 2 3; do TEST_LIBRARY=php ./run.sh PARAMETRIC tests/parametric/test_otel_span_methods.py -q || echo "ITERATION $i FAILED"; done
```
Expected: three clean runs, no "ITERATION n FAILED" line.

- [ ] **Step 5: Commit**

```bash
git add utils/docker_fixtures/_test_agent.py
git commit -m "test(parametric): log agent container creations for reuse verification"
```

---

### Task 6: Handoff note for the Platform team

Per the thread (`#... ` Slack), this POC is handed to Platform to adopt or discard. Write the rationale + scope + risks so they can evaluate without re-deriving it.

**Files:**
- Create: `docs/edit/parametric-test-agent-reuse-poc.md`

- [ ] **Step 1: Write the handoff doc**

```markdown
# POC: parametric test-agent reuse

## Why
The parametric scenario creates a fresh Docker network + test-agent + client
container per test (16 xdist workers × ~440 tests). On the shared docker-in-docker
microVM runners this churn intermittently stalls container/network setup, so a
test-agent occasionally fails to make a just-sent trace queryable within the
tracer's ~3s receipt poll → `Number (1) of traces not available, got 0`.

## What this changes
- One test-agent + one Docker network per (xdist worker, agent_env), reused
  across tests, reset with `TestAgentAPI.clear()` (`/test/session/clear`) before
  each test. Removes ~2 of the 3 create/destroy operations per test.
- The library client is unchanged: it derives its network and agent URL from the
  `test_agent` object it is handed.

## Scope / fallback
- Pools all non-snapshot tests; snapshot-marked tests keep the fresh-per-test path.
- Pool entries keyed by `agent_env`; differing envs get separate pooled agents.

## Risks to weigh before adopting
- State leakage if `clear()` is ever incomplete (traces/telemetry/RC/OTLP/sessions).
  Task 5's leakage check guards the trace case; extend it per data type before
  rolling out to all tracers.
- In-flight data: a late trace from test N arriving after test N+1's `clear()`
  could leak. Hardening path: per-test agent session tokens (requires client to
  send `X-Datadog-Test-Session-Token`).
- Shared across 9 tracers — roll out behind a flag / one language at a time.
```

- [ ] **Step 2: Commit**

```bash
git add docs/edit/parametric-test-agent-reuse-poc.md
git commit -m "docs(parametric): test-agent reuse POC handoff note"
```

---

## Self-Review

**Spec coverage** (the Slack approach = "1:1 running-agent-to-worker mapping + synchronous reset between tests"):
- One agent per worker → Task 3 (worker-keyed creator) + Task 4 (`scope="session"` = per worker). ✓
- Synchronous reset between tests → `clear()` on reuse in Task 1 + Task 4. ✓
- Halve container count / reduce contention → Tasks 3–4 (also removes the per-test network); proven in Task 5. ✓
- "Careful change / leakage risk" raised in thread → snapshot fallback (Task 4), leakage check (Task 5 Step 3), risks doc (Task 6). ✓
- Hand POC to Platform → Task 6. ✓

**Placeholder scan:** no TBD/"handle edge cases"/"similar to". The one intentional knob — which tests are poolable — is concretely defined (`get_closest_marker("snapshot")`).

**Type consistency:** `AgentLease(api, stop)`, `WorkerAgentPool(creator).acquire(request, agent_env)/shutdown()`, `agent_env_key(dict)->tuple`, `start_agent(...)->(TestAgentAPI, Callable)`, `rebind_request(request)` — used identically in Tasks 1–5. ✓

**Known limitation carried forward:** the pooled agent's *container* log (`agent_log.log`) spans the worker rather than one per test; per-test API interactions are re-pointed via `rebind_request`. Acceptable for a POC; noted in Task 6.
