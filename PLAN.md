# Wait Conditions — Incremental Reintroduction Plan

## 1. Context

### What PR #1292 tried to do

[PR #1292](https://github.com/DataDog/system-tests/pull/1292) ("Add wait
conditions to check when setup is ready"), closed unmerged in June 2024,
replaced the fixed post-setup sleep (`library_interface_timeout`,
`agent_interface_timeout`, `backend_interface_timeout`) with **precondition
checks**: instead of sleeping N seconds hoping the tracer has flushed all
data, the scenario actively polls until it observes that the expected
telemetry has arrived. When the condition is met, it proceeds immediately;
otherwise it falls back to a deadline.

The PR introduced one monolithic module `utils/wait_conditions.py` with 5
built-in conditions, plus a global registry for test-defined conditions:

1. **`_wait_for_test_requests`** (PHP only): wait until every `rid` ever
   issued by the weblog has been seen in the tracer. Needed for multi-worker
   weblogs where a single watermark request is not enough.
2. **`_wait_for_request`** (watermark): send one final `GET /` and wait until
   its trace arrives at the agent proxy. Assumption: all previous traces
   arrive before or together with the watermark. Returns the index `n` of
   the watermark message, used later as a read-after-write barrier. When a
   sampling rate is set, issues a new watermark request each poll cycle
   (because any single request may be dropped).
3. **`_wait_for_request_in_agent`**: same idea, one level deeper — wait
   until the watermark request is also visible on the agent interface, not
   just the tracer's.
4. **`_wait_for_telemetry`**: after the watermark index, wait for 2 more
   telemetry heartbeats. Two heartbeats after the watermark means anything
   batched into telemetry before the watermark has had time to be flushed.
   Special-cased to short-circuit when telemetry isn't emitted at all (Ruby
   only sends some messages but not heartbeats).
5. **`_wait_for_remote_config`**: if `proxy_state.mock_remote_config_backend`
   is set, wait until `len(MOCKED_RESPONSES) + 2` config requests have been
   seen — enough to guarantee every mocked RC response was delivered.
6. **`_wait_for_otel_request`**: OTel-specific watermark based on
   `/basic/trace`.
7. **Custom conditions**: tests can call `wait_conditions.add(timeout, fn)`
   to register arbitrary boolean callables (used by DSM and profiling).

It also made collateral changes:

- Renamed three per-interface timeouts into a single `post_setup_timeout`.
- Added `post_setup=True` to `weblog.request()` to allow a watermark request
  outside the setup phase (normally forbidden).
- Added `weblog.get_all_seen_rids()` and `interfaces.library.get_all_rids()`.
- Tightened `DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS` to 1s for many RC
  scenarios so the watermark converges faster.
- Removed per-interface `wait()` methods and `_init_rid_to_library_trace_ids`
  on the backend interface.
- Added `cpuset_cpus="0"` when starting containers (unrelated cgroup tweak).
- Enabled DSM/profiling wait conditions in the corresponding tests.

### Why it didn't merge

The PR's own description lists open TODOs — "Move most logic to
`wait_conditions.py`", `/make_distant_call` compatibility, documentation of
_why_ the conditions actually work — and there are no review comments, no
CI runs recorded, and the branch was closed a year after the last commit.
Reading the diff with 2.5 years of hindsight, the likely blockers were:

- **Big-bang semantics change**: 11 files modified, the wait model replaced
  globally, behavior redefined for every scenario at once. Hard to bisect
  if a single library starts flaking.
- **Global mutable state**: `_WAIT_CONDITIONS` is a module-level list. Any
  cross-scenario pollution (e.g. a condition added during one test and not
  drained) silently affects the next scenario in the same process.
- **Polling under the GIL**: `while True: list(interfaces.library.get_data())`
  materializes the entire `_data_list` on every iteration. Today we already
  have an **event-driven** `Interface.wait_for(predicate, timeout)` that
  wakes up from `_append_data` — polling would be a regression.
- **Assumptions not yet justified**: "2 heartbeats after watermark is
  enough", "sampling rate + new request per iteration is correct",
  "agent-side watermark subsumes backend wait". None of these were
  documented or tested in isolation.
- **PHP fallback silently broken**: `_wait_for_test_requests` loops with
  no `time.sleep`, burning CPU while contending with the ingest path.
- **No wait for E2E backend**: despite the checkbox, the PR actually
  *removed* `backend_interface_timeout` without replacing its single known
  use case (APM tracing E2E, which waits for backend lookups by trace ID).
- **Changed test contract**: `test_dsm.py` now reads hashes in `setup_*` and
  stores them on `self`, then asserts on `self.r.status_code == 200` too.
  That is the right direction but it's a separate, large refactor entangled
  with the wait refactor.

### What has changed in the codebase since April 2024

The tree has moved on:

- `utils/_context/_scenarios.py` has been split into a package
  (`utils/_context/_scenarios/*.py`). The per-interface timeouts still
  exist in `endtoend.py:195-205, 284-327, 466-470` and in every scenario
  declaration in `__init__.py` and `debugger.py`.
- `Interface.wait_for(predicate, timeout)` is **already implemented**
  (`utils/interfaces/_core.py:199-222`) and used by several tests:
  `_remote_config.py`, `tests/ffe/test_dynamic_evaluation.py`,
  `tests/debugger/utils.py`, `tests/stats/test_stats.py`,
  `tests/test_sampling_rate_capping.py`,
  `tests/remote_config/test_remote_configuration.py`, and more.
- The interface base class owns a `threading.Event` and dispatches it on
  every `_append_data`, so predicate-based waits wake up as soon as the
  matching payload arrives — no polling required.
- Replay mode is well established: `load_data_from_logs()` is the codepath
  used for replay, and `post_setup()` branches on `self.replay`.
- `force_interface_timout_to_zero` exists to skip waiting when no test was
  collected.
- `_wait_for_app_readiness()` exists as a pre-setup warmup and uses
  `interfaces.library.ready.wait(40)` — a different `ready` event we can
  reuse.
- `containers.py` has moved, `_fix_host_pwd_in_volumes` is gone from the
  path the PR touched, and `cpuset_cpus="0"` is **not something we want**
  — it would pin every container to one CPU.

### Goals

The underlying idea is still valuable: **replace opaque sleeps with
explicit, observable conditions**. That makes CI faster when everything
works, more deterministic when it doesn't, and gives us a single place to
encode "what does 'setup is finished' really mean for scenario X".

This plan aims to deliver the same end state as PR #1292, but:

1. **Strictly additive** at every step — existing `interface.wait(timeout)`
   keeps working until the last step removes it.
2. **Event-driven** — reuse the existing `Interface.wait_for` and its
   `threading.Event`, do not reintroduce the PR's busy polling.
3. **Scoped per scenario class** — no module-level global registry; the
   conditions live on the scenario instance and are drained per run.
4. **One library, one RFC flag at a time** — the risky behavior changes
   (telemetry-heartbeat barrier, sampling-mode watermark) land behind a
   scenario-level opt-in before becoming the default.
5. **Documented assumptions** — every condition answers the question
   "why is this sufficient?" in a comment next to the code.
6. **Leave out the unrelated changes** — no `cpuset_cpus`, no `stop(timeout)`
   change, no container log tweaks, no `DD_REMOTE_CONFIG_POLL_INTERVAL`
   overrides unless we can show they are actually needed for the wait to
   converge.

### Non-goals

- Rewriting the DSM or profiling tests. If the existing fixed timeout is
  enough for them today, leave them alone; the wait-condition API will be
  available if they opt in later.
- Changing the pre-setup warmup / app-readiness path.
- Changing behavior in replay mode.
- Removing `tracer_sampling_rate` or `proxy_state` plumbing.
- Removing `_wait_for_app_readiness`.

---

## 2. Design

### 2.1 Module layout

```
utils/
  wait_conditions/
    __init__.py          # public API: WaitConditions, Condition
    _watermark.py        # one watermark request + per-interface observation
    _telemetry.py        # "N heartbeats after watermark" barrier
    _remote_config.py    # RC-count barrier, driven by proxy_state
    _otel.py             # /basic/trace watermark
    README.md            # why each condition is sufficient
```

A package, not a single module. Each condition is isolated and
independently testable. No module-level mutable state.

### 2.2 Public API

```python
# utils/wait_conditions/__init__.py

@dataclass(frozen=True)
class Condition:
    """One thing we are waiting for.

    `predicate` is called with no arguments; it should return True when the
    condition is met. Implementations should be cheap and idempotent.
    `description` is used in log lines and error messages.
    """
    predicate: Callable[[], bool]
    description: str
    timeout: float  # seconds

class WaitConditions:
    """Collects and runs a set of wait conditions for one scenario run.

    Instances are owned by a scenario; nothing is shared across scenarios or
    across processes.
    """

    def __init__(self) -> None: ...

    def add(self, condition: Condition) -> None: ...

    def run(self, *, deadline: float) -> list[Condition]:
        """Run every registered condition in parallel (thread-per-condition
        on top of the existing interface events). Returns the list of
        conditions that did not meet before the deadline.
        """
```

Key differences from PR #1292's `_WAIT_CONDITIONS` global:

- **Instance-scoped.** The scenario holds one `WaitConditions` for the
  current run. After `post_setup` returns, it is dropped. There is no
  risk of leaking a condition from one scenario into the next.
- **Concurrent.** Every condition is waited on in its own thread, bounded
  by the scenario-level deadline. Sequential waits made sense in the
  original PR because the conditions were ordered (watermark first, then
  telemetry_after_watermark). Here we keep ordering where it matters
  (telemetry references the watermark index) by composing conditions in
  code rather than by relying on a list order.
- **No polling in the hot loop.** Each built-in condition builds on
  `Interface.wait_for(predicate, timeout)`, which already wakes up on
  `_append_data`. Custom conditions passed as raw callables still poll,
  but at a much lower rate and only when the user opts in.

### 2.3 Scenario integration

The scenario's `_wait_and_stop_containers` currently does:

```python
self._wait_interface(interfaces.library, library_interface_timeout)
...
self._wait_interface(interfaces.agent, agent_interface_timeout)
...
self._wait_interface(interfaces.backend, backend_interface_timeout)
```

We keep that shape. We add an optional earlier step:

```python
self._wait_for_setup_conditions(deadline=time.time() + self.post_setup_timeout)
# then the existing per-interface waits, with their timeouts clamped to the
# remaining budget
```

The existing interface-level timeouts become a **fallback**, not the
primary mechanism. We do **not** delete them in the first steps.

### 2.4 Why each condition is sufficient

This section is the one that was missing from PR #1292. It goes into
`utils/wait_conditions/README.md`.

- **Watermark trace**: We issue `GET /` after setup requests are done and
  wait until the tracer has flushed a trace containing the resulting `rid`.
  The trace pipeline is FIFO per worker process (this is a property of the
  agent writer, not of the library under test), so any span generated
  **before** the watermark request by the same worker has already been
  sent to the agent proxy by the time we observe the watermark. This is
  why multi-worker weblogs (php-fpm, Apache mod_php, passenger on Ruby if
  we ever add it) need the full-rid pre-pass.
- **Watermark in agent**: Observing the watermark on the tracer proxy only
  proves the tracer flushed. The agent may still be batching before
  sending to the backend proxy. So we wait for the watermark span to
  appear on the agent interface too. This subsumes what
  `_wait_interface(interfaces.agent, ...)` was buying us in the current
  code, for trace data.
- **Telemetry heartbeat barrier**: Telemetry is emitted on a wall-clock
  timer, not per-request. So the watermark trace does not tell us
  anything about telemetry that was due but not yet flushed. The
  "heartbeat" message is the one message that is guaranteed to be
  periodic regardless of request activity. Two heartbeats after we
  observed the watermark is enough to guarantee that: (a) at least one
  full heartbeat period has elapsed since the last request, (b) any
  batched telemetry generated by any pre-watermark request has had one
  full period to be flushed, plus one more period as safety. One is too
  few because heartbeat #1 could have been in-flight when the watermark
  was observed. Libraries that never send heartbeats (Ruby) are detected
  by the absence of heartbeat or app-started messages and short-circuit
  this wait.
- **Remote config count**: The mock RC backend is deterministic — it has
  exactly `len(MOCKED_RESPONSES)` payloads to deliver. Once we've seen
  `len(MOCKED_RESPONSES) + 2` config requests from the library, the
  library has ack'd every payload plus two additional polls confirming
  "no new update". This is the classic "two consecutive no-ops prove
  we're caught up" pattern. The `+2` is not arbitrary: one poll could
  race with the last mocked response being applied; two polls after the
  last mocked response are necessary to observe the applied ack.
- **OTel watermark**: Same as trace watermark, but on `/basic/trace` via
  the OTel collector pipeline, observed on
  `interfaces.open_telemetry`.
- **Backend wait** (APM tracing E2E only): Today this uses
  `backend_interface_timeout=5`. For the backend there is no cheap
  watermark — the backend does not offer a "last-seen-rid" API we can
  observe. The existing fixed sleep is the right shape here; wait
  conditions should **not** try to replace it. We keep
  `backend_interface_timeout` as is and, when we retire
  `library_interface_timeout` and `agent_interface_timeout`, leave
  `backend_interface_timeout` untouched.

### 2.5 What we do not reintroduce from PR #1292

- **Global `_WAIT_CONDITIONS` list** — replaced by the per-scenario
  `WaitConditions` instance.
- **Busy polling** — replaced by `Interface.wait_for` + one bounded thread
  per condition.
- **`cpuset_cpus="0"`** — unrelated, actively harmful on multi-CPU runners.
- **`container.stop(timeout=10)`** — unrelated.
- **Bulk `DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS=1`** — reintroduced only
  on scenarios where step 6 empirically shows the watermark doesn't
  converge within the old timeout.
- **`DD_TELEMETRY_METRICS_INTERVAL=2`** — same as above, empirical only.
- **`get_rid_from_request` accepting a raw string** — small footgun,
  unrelated to wait logic.
- **Removal of `_init_rid_to_library_trace_ids`** from the backend
  interface — we will keep the `wait()` path alive on `_backend.py`.

---

## 3. Plan — one PR per step

Each step is small enough to review and run CI in isolation. Each step
**leaves the tree green and the behavior unchanged for anything not
explicitly opted in**.

### Step 0 — Baseline measurements

Before any change, record current `post_setup` durations per scenario
from a main-branch CI run (dashboard or pytest log scrape). This is the
number we are trying to beat. Commit nothing; file an internal note.

**Deliverable**: a list of "scenario → median post_setup wait time on
main" numbers we can use as the before/after baseline.

### Step 1 — Skeleton `wait_conditions` package, no behavior change

- Create `utils/wait_conditions/__init__.py` with `WaitConditions` and
  `Condition` as described in §2.2.
- `WaitConditions.run()` is a no-op in this step (returns `[]`).
- No other file changes, no scenario integration.
- Unit tests in `utils/wait_conditions/test_wait_conditions.py`:
  - Adding and iterating conditions.
  - `run()` with trivially-true / trivially-false predicates and a 100 ms
    deadline.
  - Thread safety: `add()` concurrent with `run()`.

**Acceptance**: `pytest utils/wait_conditions` passes in CI; default
scenario still runs identically.

### Step 2 — Watermark condition on the tracer interface

- Add `_watermark.py` with `make_tracer_watermark(*, library_name,
  tracer_sampling_rate, weblog, interfaces) -> Condition`.
- Implementation uses `interfaces.library.wait_for(predicate,
  timeout)` — event-driven, no polling.
- Issue the watermark request via `weblog.get("/",
  post_setup=True)` — so we add `post_setup=True` support to
  `_weblog.py` here, exactly the change from PR #1292 (minimal, no other
  surface change).
- For sampling scenarios, predicate retries the watermark request every
  `_ITER_SLEEP_TIME` (see §2.6 below) by scheduling a helper that calls
  `wait_for` in a loop, giving up at the deadline.
- Scenario **does not yet use this**; it only becomes testable via a
  new `EndToEndScenario.wait_conditions_enabled = False` flag that is
  off everywhere.
- Add `tests/internal/test_wait_conditions_watermark.py` as an integration
  test using the lightest existing scenario (`DEFAULT` on one library,
  e.g. python) — enable the flag locally in the test only.

**Acceptance**: with the flag on, setup completes faster than baseline
on python DEFAULT; with the flag off (everywhere else), zero behavior
change.

### Step 3 — Watermark condition on the agent interface

- Add `make_agent_watermark(...)` in `_watermark.py`. Predicate reads
  from `interfaces.agent.get_spans(request=rid)`.
- Runs after the tracer watermark (composition: the agent predicate only
  starts checking once tracer `rid` is known).
- No scenario change yet; same flag as step 2.

**Acceptance**: agent-side wait converges on python DEFAULT with the
flag on; no change otherwise.

### Step 4 — Telemetry heartbeat barrier

- Add `_telemetry.py` with `make_telemetry_barrier(*, interfaces,
  watermark_index) -> Condition`.
- "Watermark index" is the `n` returned in §2.4. We expose it from the
  tracer-watermark condition via a shared mutable container (`dict` or
  small dataclass) that step 2 stored the index into.
- Short-circuit: if no `app-heartbeat` or `app-started` has ever been
  seen, `Condition.predicate` returns True immediately.

**Acceptance**: on python DEFAULT and node DEFAULT, telemetry barrier
is reached; on ruby DEFAULT, the short-circuit fires and setup does not
stall.

### Step 5 — Opt-in at scenario level on DEFAULT only

- Add `EndToEndScenario.__init__` parameter `use_wait_conditions: bool =
  False`.
- When True, `_wait_and_stop_containers` builds a `WaitConditions` with
  the three conditions from steps 2–4, runs them with
  `deadline=time.time() + self.library_interface_timeout + self.agent_interface_timeout`,
  and **then still calls** the existing `_wait_interface(...)` waits with
  a timeout clamped to `max(0, deadline - time.time())`. If the wait
  conditions all succeeded, the legacy waits are cheap no-ops.
- Turn the flag on for `scenarios.default` only.
- `backend_interface_timeout` remains untouched, so APM_TRACING_E2E is
  not affected.

**Acceptance**: full default-scenario CI passes across every library and
weblog. Compare `post_setup` times to Step 0 baseline; expected drop on
libraries with short actual flush times (nodejs, go) and roughly equal
on ones that were already tight (java, python-at-25s).

### Step 6 — Remote-config condition

- Add `_remote_config.py` with `make_rc_barrier(*, proxy_state,
  interfaces) -> Condition | None`. Returns `None` if there is no
  `mock_remote_config_backend` — caller filters out `None`.
- Opt in on one RC scenario:
  `REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES`.
- If the wait reliably converges, opt in on the other RC scenarios in a
  follow-up (one per PR is overkill; they all share the same shape).
- Only now consider whether to override `DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS`.
  Decide based on measured convergence time, not by blanket-copying PR
  #1292.

**Acceptance**: RC scenarios finish setup faster than their current
`library_interface_timeout=100`.

### Step 7 — OTel watermark

- Add `_otel.py` with `make_otel_watermark(...)`.
- Opt in on `OpenTelemetryScenario` via `use_wait_conditions=True`.
- `backend_interface_timeout` still applies for the OTel collector →
  backend path that OTel scenarios use.

**Acceptance**: OTel integrations scenario still green; setup faster.

### Step 8 — Custom condition support, port DSM and profiling

- Expose `scenario.wait_conditions.add(Condition(...))` to tests via a
  new context helper `utils.wait_conditions.add_for_current_scenario(...)`
  — the helper retrieves the current scenario (same pattern the existing
  `context` uses) rather than relying on a global list.
- Port `tests/integrations/test_dsm.py::DsmHelper.wait_for_hashes` to
  register conditions through this helper.
  - Keep the hash-on-`self` refactor — it's good on its own merit — but
    split it out into its own PR if the diff is noisy.
- Port `tests/test_profiling.py::_common_setup` to register a profiling
  condition the same way.

**Acceptance**: DSM and PROFILING scenarios still green; observable
speedup only on passing runs.

### Step 9 — Opt in across all EndToEnd scenarios

- Flip `use_wait_conditions=True` to be the default in
  `EndToEndScenario.__init__`. Scenarios that needed the old behavior
  (if any surfaced in Step 5) remain pinned to `False` with an inline
  `# TODO: opt in` comment and a JIRA link.
- Keep `library_interface_timeout`, `agent_interface_timeout`, and
  `backend_interface_timeout` and their role as fallback.

**Acceptance**: full CI green across all scenarios. Dashboard-level
post-setup time compared against Step 0.

### Step 10 — Retire the fallbacks (optional, only if Steps 5–9 are stable for at least two weeks)

- Remove `library_interface_timeout` and `agent_interface_timeout`
  parameters from `EndToEndScenario`. They become `post_setup_timeout`
  (scenario-level deadline for wait-conditions).
- `backend_interface_timeout` stays — it has no watermark.
- `interfaces.library.wait(timeout)` and `interfaces.agent.wait(timeout)`
  are deleted. `interfaces.backend.wait(timeout)` stays.
- Delete the per-library timeout table in `endtoend.py:312-327`.
- Update `docs/edit/flushing.md`, `docs/internals/end-to-end-life-cycle.md`.

**Acceptance**: diff is purely mechanical; CI green; dashboards unchanged.

### 2.6 Polling interval

The PR used `_ITER_SLEEP_TIME = 0.5`. For everything that goes through
`Interface.wait_for`, there is no polling — the event is set by
`_append_data`. The only place a loop is needed is the
sampling-with-retries watermark (step 2). There, `1.0s` matches the
minimum request interval the ingest path tolerates (comment in the
original code). Use `1.0s` and note the justification.

---

## 4. Test strategy

- **Unit**: `utils/wait_conditions/test_*.py` — pure-Python, no docker,
  mock the interfaces.
- **Integration** per step: one minimal scenario, one library, flag
  on, behavior verified in isolation. Run in `run-default-scenario` only
  at first.
- **Full**: once a step flips a default, the `run-default-scenario`
  label is removed on that PR so every scenario runs.
- **Measurement**: grep pytest output for the `[post_setup]` log lines
  we emit from `WaitConditions.run()` and compare medians per
  (scenario, library, weblog) to Step 0 baseline.

---

## 5. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A library's trace pipeline is **not** FIFO end-to-end (e.g. async buffer with reorder) and watermark arrives before an earlier trace. | Step 5 is gated by CI on every library; any flake during the stabilization window pins that library back to legacy waits via `use_wait_conditions=False` until investigated. |
| Telemetry "2 heartbeats" assumption breaks in a library we forgot. | Short-circuit keyed on heartbeat/app-started presence (same as PR #1292). Add a warning log when the short-circuit fires so we notice silent failures. |
| `post_setup=True` request path diverges from normal `weblog.get` in a subtle way and tests start seeing it as a real request. | Keep the "don't append to `responses`" gate. Add an assertion in the weblog that a `post_setup=True` request is only allowed from `utils/wait_conditions/**`. |
| Thread-per-condition explodes under high scenario count. | Bounded: at most 5 conditions per scenario; threads use `Interface.wait_for`, which itself doesn't spin. Worst case is <10 threads per scenario, short-lived. |
| Pollution across tests within a scenario via the per-scenario `WaitConditions`. | `WaitConditions` instance is created in `post_setup` and dropped after `run()`. Conditions registered by a test apply only to that scenario's post-setup, which is exactly what we want. |
| Someone lands a new scenario without opting in after Step 9. | Step 9 flips the default, so new scenarios get wait conditions automatically. Legacy fallbacks still there as safety net until Step 10. |
| Step 10 removes `library_interface_timeout` and some forgotten external tool parses it. | Step 10 is gated on a two-week green window and a repo-wide grep. |

---

## 6. What PR #1292 got right and we should keep

- Watermark request idea — good and cheap.
- `post_setup=True` flag on `weblog.request()` — minimal and correct.
- Telemetry barrier as a separate step from trace barrier — correct.
- Short-circuit for libraries that don't emit telemetry — correct.
- `get_all_rids()` / `get_all_seen_rids()` — useful for the PHP case;
  scope them to the PHP path only in our version.
- Custom wait conditions as an extension point — correct, but
  re-scoped to a per-scenario collection.

## 7. What PR #1292 got wrong and we should not repeat

- One big module with global state.
- Busy polling instead of using `Interface.wait_for`.
- Merging unrelated container/cgroup changes.
- Deleting `backend_interface` wait semantics without a replacement.
- Global `DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS` overrides without
  measurement.
- Entangling the DSM test refactor with the wait refactor.
- No documentation of _why_ each condition is sufficient.
- No incremental opt-in flag.

---

## 8. Open questions to resolve before Step 1

1. Is `Interface.wait_for` robust enough that we can lean on it as the
   primary mechanism? (Look at the existing call sites in
   `tests/debugger`, `tests/stats`, `tests/remote_config` to confirm.)
2. Is there a library where `GET /` is not routable (some weblog
   variants may not define `/`)? If so, the watermark endpoint needs
   to be `/watermark` and every weblog needs a trivial handler. If that
   is too invasive, we fall back to issuing a request whose path
   already exists in every weblog — candidates: `/healthcheck` if
   present, otherwise re-use a known path from the setup phase by
   replaying it (harder, don't do this in v1).
3. Do we need a kill-switch env var (`SYSTEM_TESTS_WAIT_CONDITIONS=0`)
   to force-disable the new path on a CI run without a code change?
   Yes, add it in Step 5.
