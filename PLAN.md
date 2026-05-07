# Wait Conditions

## Goal

Replace the per-interface fixed sleeps in `EndToEndScenario._wait_and_stop_containers`
(`library_interface_timeout`, `agent_interface_timeout`, `backend_interface_timeout`)
with **explicit, observable conditions** registered during setup and checked
exactly once after all setup phases complete.

The end state is:

- A small `utils/wait_conditions.py` module exposing a `Condition` dataclass and
  a process-global registry (`add`, `clear`, `iter_conditions`, `run`).
- A handful of built-in condition factories for the situations that recur:
  watermark traces (tracer/agent/OTel), telemetry-message-count barriers,
  remote-config message-count barriers, and arbitrary "user supplied" predicates.
- Every condition wired to `Interface.wait_for(predicate, timeout)` so it
  wakes up on `_append_data` and never busy-polls.
- `EndToEndScenario` runs the registry once, between the last setup phase and
  the first test assertion, with a single global deadline.
- The current per-interface timeouts shrink to `0` (or are removed entirely)
  for proxied scenarios, but `backend_interface_timeout` stays — there is no
  cheap watermark for the backend.

The plan below assumes the worktree is reset to a state with **none** of the
current WIP commits applied. Each step lands as one PR and leaves the tree
green for everything not explicitly opted in.

---

## Design

### Module shape

```
utils/wait_conditions.py
```

Single module. If it grows past ~400 lines we split per-condition-family later.
The registry is module-level and process-global because tests register
conditions in their `setup_*` methods, and `post_setup` runs them after every
`setup_*` has run.

### API

```python
@dataclass(frozen=True)
class Condition:
    wait: Callable[[float], bool]   # called with effective timeout, returns True iff met
    description: str
    timeout: float                  # per-condition cap, in seconds

def add(condition: Condition) -> None: ...
def clear() -> None: ...
def iter_conditions() -> Iterator[Condition]: ...
def run(*, deadline: float) -> list[Condition]: ...
```

`run()` iterates conditions in registration order. Before each call it computes
`effective = min(condition.timeout, max(0.0, deadline - time.time()))` and
invokes `condition.wait(effective)`. **Every condition is called at least once,
even if `effective == 0`** — the timeout only controls how long we wait for
new data after the first cheap check has failed. Conditions that return `False`
are appended to the returned list; the runner does not raise.

### Built-in conditions

Each built-in lives in `wait_conditions.py` as a `make_*` factory that returns
a `Condition`. The wait function:

1. Performs one synchronous check against the data already captured.
2. If that check fails and `effective_timeout > 0`, calls
   `interface.wait_for(predicate, effective_timeout)`. `Interface.wait_for`
   wakes up on `_append_data`, so this is event-driven, not polled.
3. Performs the synchronous check one more time and returns its boolean result.

This pattern applies to the tracer watermark, agent watermark, OTel watermark,
telemetry-count barrier, and RC-count barrier. Anything that genuinely cannot
hook into an interface event uses a tiny retry helper with a 1.0s sleep
between attempts; the only built-in that needs this today is the
sampling-mode tracer watermark, where each retry sends a fresh request because
any single request may be sampled out.

### Why each condition is sufficient

These rationales live as docstrings next to each factory in
`utils/wait_conditions.py`. They do not duplicate into a separate doc.

- **Tracer watermark trace**. After all setup requests, send `GET /` with the
  reserved `post_setup=True` flag. Wait until the tracer has flushed a span
  for the resulting `rid`. The trace pipeline is FIFO per worker process, so
  any span generated **before** the watermark request by the same worker has
  already been pushed to the agent proxy by the time we observe the watermark.
  Multi-worker weblogs (php-fpm, Apache mod_php) need the per-worker variant
  described below.
- **Agent watermark trace**. Observing the watermark on the tracer interface
  only proves the tracer flushed. Wait until the same `rid` is also visible
  on `interfaces.agent`. This subsumes most of what `agent_interface_timeout`
  was buying us for trace data.
- **OTel watermark**. Same shape but on `/basic/trace` via the OTel pipeline,
  observed on `interfaces.open_telemetry`.
- **Telemetry message-count barrier**. Telemetry is wall-clock timer driven,
  not request driven. `app-heartbeat` is the one message guaranteed to be
  periodic regardless of request activity. Asking for "N heartbeats per
  runtime" guarantees: (a) at least N-1 full heartbeat periods have elapsed
  on each worker, (b) anything batched into telemetry before the first
  heartbeat we observed has had time to be flushed. Libraries that never
  emit heartbeats (Ruby) are detected via the absence of any
  `app-heartbeat`/`app-started` and short-circuit to True.
- **Remote-config count barrier**. The mock backend is deterministic with
  exactly `len(MOCKED_RESPONSES)` payloads. Once the library has issued
  `len(MOCKED_RESPONSES) + 2` config requests, every payload has been ack'd
  plus two no-op polls confirm "we're caught up". `+2` is needed because one
  of the polls could race with the last mocked response being applied.
- **PHP per-worker watermark**. php-fpm has multiple PHP worker processes
  feeding one shared library exporter. A single watermark request only proves
  the worker that handled it has flushed; other workers may have older data
  pending. The condition collects all `rid`s the weblog has issued during
  setup (`weblog.get_all_seen_rids()`), waits until every one of them has been
  observed on `interfaces.library`, and only then proceeds. This is the
  PHP-specific replacement for the watermark trace.
- **Backend wait**. There is no cheap backend-side watermark. `backend_interface_timeout`
  stays as a fixed sleep. Wait conditions do not try to replace it.

### Scenario integration

`EndToEndScenario.__init__` gets one new parameter:

```python
use_wait_conditions: bool = False
```

When `False`, behavior is unchanged and the registry is not consulted. When
`True`, `_wait_and_stop_containers` calls `_wait_for_setup_conditions(...)`
between the last `setup_*` invocation and `weblog_infra.stop()`. The runner
uses `deadline = time.time() + post_setup_timeout`, where
`post_setup_timeout = library_interface_timeout + agent_interface_timeout`
during the rollout (single deadline for the new world, but kept as a sum so
the existing per-interface tunings continue to apply).

After `wait_conditions.run(...)` returns, we still call the existing
`_wait_interface(library, 0)` / `_wait_interface(agent, 0)` paths. They become
cheap no-ops when conditions all succeeded; if some condition timed out, the
fallback may still close the gap. `_wait_interface(backend, backend_interface_timeout)`
is unchanged regardless.

### Validation

We have two complementary tools:

- **`./run.sh <SCENARIO> [TEST_NODEID]`**: standard end-to-end execution.
  Tightest feedback loop for "did this scenario regress on this library".
- **`utils/scripts/run_isolated_matrix.py`**: one-shot matrix runner. For each
  `(library, weblog_variant)` it builds once, then for each `(scenario, test)`
  it issues a single `./run.sh SCENARIO test_nodeid` and appends the result to
  `logs_isolated_matrix/results.jsonl`. Use this to:
    - Establish a baseline (run on `main` or before opting in).
    - Re-run the same matrix after the change.
    - Diff JSONL records by `(library, weblog, scenario, test, status)` to
      surface any regression. `--resume` skips already-recorded entries.

The plan below specifies acceptance criteria per step, leaving the choice of
"single scenario locally" vs "matrix runner" to whoever lands the PR. Steps
that flip a default for many libraries should use the matrix runner before
landing.

---

## Steps

Each step is one PR. Each PR is **strictly additive** for anything not opting
in via `use_wait_conditions=True`.

### Step 1 — Skeleton module + sequential runner + unit tests

**Files**: `utils/wait_conditions.py` (new), `tests/test_the_test/test_wait_conditions.py` (new).

**What to implement**:

1. `utils/wait_conditions.py`:
    - `Condition` dataclass (frozen) with fields `wait`, `description`, `timeout`.
    - `_CONDITIONS: list[Condition] = []` at module level.
    - `add`, `clear`, `iter_conditions`, `run` as described in the API section.
    - `run`:
        - Iterates `_CONDITIONS` in registration order.
        - Before each: computes `effective = min(condition.timeout, max(0.0, deadline - now))`.
        - Calls `condition.wait(effective)`.
        - Logs success/failure via `utils._logger.logger.info` / `logger.warning`.
        - Collects and returns failures.
2. `tests/test_the_test/test_wait_conditions.py`, marked
   `pytest.mark.scenario("TEST_THE_TEST")`, `clear_wait_conditions` autouse
   fixture, covering:
    - `add` + `iter_conditions` round-trip; `clear` empties the registry.
    - `run` calls conditions in registration order.
    - `run` clamps `effective_timeout` to remaining global budget.
    - `run` always invokes `wait` at least once even when budget is exhausted
      (advance `time.time()` via `monkeypatch` past the deadline before the
      second condition runs and assert it was still called with `0.0`).
    - `run` returns the list of failed conditions, in registration order.

**No** scenario file is touched. Nothing imports `wait_conditions` outside the
test file.

**Acceptance**: `./run.sh TEST_THE_TEST tests/test_the_test/test_wait_conditions.py`
passes locally; rest of CI unchanged.

---

### Step 2 — Tracer watermark factory + `weblog.post_setup=True` plumbing

**Files**: `utils/wait_conditions.py`, `utils/_weblog.py`,
`tests/test_the_test/test_wait_conditions.py`.

**What to implement**:

1. `utils/_weblog.py`:
    - Add a `post_setup: bool = False` keyword to `_Weblog.request()` (or wherever
      the request entry point lives).
    - When `post_setup=True`, perform the request normally but **do not** append
      it to `self.responses`. Document the rationale inline: post-setup
      requests are watermarks, not test inputs, and adding them to `responses`
      would corrupt assertions that count requests.
    - Assert `inspect.stack()` originates from `utils/wait_conditions.py` (or a
      registered allowlist) when `post_setup=True`. Cheap belt-and-braces against
      misuse from test code.
2. `utils/wait_conditions.py`:
    - Add `make_tracer_watermark(*, weblog, interfaces, endpoint="/", timeout=DEFAULT_CONDITION_TIMEOUT) -> Condition`.
    - Implementation:
        - Issue `weblog.get(endpoint, post_setup=True)`. Capture the response (or
          its `rid`) in a closure.
        - Define `request_has_trace()` that calls
          `interfaces.library.get_spans(request=response)` and returns whether
          any span exists.
        - First check: synchronous `request_has_trace()`. If True, return True.
        - If `effective_timeout > 0`, call
          `interfaces.library.wait_for(lambda data: request_has_trace(), effective_timeout)`.
          The predicate body re-checks captured data; we ignore `data` because
          `wait_for` already wakes up on every `_append_data`.
        - Second check: synchronous `request_has_trace()` again. Return that result.
    - The factory signature avoids importing `weblog` / `interfaces` at module
      load time so it stays unit-testable with fakes.
3. **Sampling-mode variant** (skip if no scenario has
   `tracer_sampling_rate < 1.0`): add an internal helper that loops with
   `time.sleep(1.0)` between iterations, sending a new `weblog.get(endpoint, post_setup=True)`
   on each iteration. Each iteration uses the standard "first cheap check,
   then `wait_for` with shrinking budget" pattern so we don't busy-poll between
   requests. Only enable in the factory if `tracer_sampling_rate is not None`.
4. Unit tests in `tests/test_the_test/test_wait_conditions.py`:
    - Tracer watermark succeeds when an existing trace is already captured
      (no `wait_for` call).
    - Tracer watermark waits for the trace and succeeds when it arrives.
    - Tracer watermark with `effective_timeout=0` checks once and reports failure.
    - `weblog.post_setup=True` does not append to `responses`.
    - `weblog.post_setup=True` from a forbidden caller raises (or asserts).

**No** scenario file is touched. Acceptance: unit tests pass; nothing else
calls `make_tracer_watermark` yet.

---

### Step 3 — Scenario integration with opt-in flag (DEFAULT only)

**Files**: `utils/_context/_scenarios/endtoend.py`,
`utils/_context/_scenarios/__init__.py` (only the `DEFAULT` declaration).

**What to implement**:

1. `EndToEndScenario.__init__`:
    - New parameter `use_wait_conditions: bool = False`.
    - Store `self._use_wait_conditions = use_wait_conditions`.
    - Compute and store `self._post_setup_timeout = library_interface_timeout + agent_interface_timeout`
      after the per-library default resolution block at line 315.
2. `EndToEndScenario._wait_and_stop_containers` (the `else` branch,
   non-replay path), insert before `self.weblog_infra.stop()`:
    ```python
    if self._use_wait_conditions and not force_interface_timout_to_zero:
        self._wait_for_setup_conditions(deadline=time.time() + self._post_setup_timeout)
    ```
3. New method:
    ```python
    def _wait_for_setup_conditions(self, *, deadline: float) -> None:
        if not self._use_proxy_for_weblog:
            return
        wait_conditions.add(
            wait_conditions.make_tracer_watermark(
                weblog=weblog,
                interfaces=interfaces,
                timeout=max(0.0, deadline - time.time()),
            )
        )
        logger.terminal.write_sep("-", f"Wait for setup conditions ({self._post_setup_timeout}s)")
        logger.terminal.flush()
        failed = wait_conditions.run(deadline=deadline)
        for condition in failed:
            logger.warning(f"Setup condition timed out: {condition.description}")
    ```
4. The legacy `_wait_interface(interfaces.library, ...)` call is left in place,
   **but** when `self._use_wait_conditions` is True, it is invoked with
   `timeout=max(0, int(deadline - time.time()))` so that any remaining global
   budget is still spent on the legacy fallback. This keeps the safety net.
5. Flip `use_wait_conditions=True` only on `scenarios.default` in
   `utils/_context/_scenarios/__init__.py`. Every other scenario keeps the
   default `False`.
6. `wait_conditions.clear()` is called from `_wait_for_setup_conditions` at
   entry, before any `add()`, so re-running setups in the same process (rare
   but possible) doesn't accumulate conditions across scenarios.

**Acceptance**:

- Run `DEFAULT` locally for each library that builds:
  ```
  for lang in python nodejs java ruby php golang dotnet cpp_httpd cpp_nginx cpp_kong; do
      ./build.sh $lang && ./run.sh DEFAULT
  done
  ```
  All pass.
- For at least one library, run with `use_wait_conditions=False` (set by
  temporarily reverting the `__init__.py` flag) and confirm pass count is
  unchanged. This guards against silent regressions in the legacy path.
- (Optional) `utils/scripts/run_isolated_matrix.py --scenario DEFAULT` baseline
  vs. with-flag, diff JSONL.

If the PHP `Test_Telemetry::test_app_heartbeats_delays` failure surfaces here
(it does in the current WIP), it is **expected**. Document the failure in the
PR description and resolve it in Step 5; do not paper over it by silently
extending the timeout.

---

### Step 4 — Agent watermark factory + register it on DEFAULT

**Files**: `utils/wait_conditions.py`, `utils/_context/_scenarios/endtoend.py`,
`tests/test_the_test/test_wait_conditions.py`.

**What to implement**:

1. `make_agent_watermark(*, weblog, interfaces, endpoint="/", timeout=...) -> Condition`.
    - Reuses the same `weblog.get(endpoint, post_setup=True)` request — but
      since the tracer watermark already issued one, we want them to share. Two
      ways to do this, pick the simpler:
        - **Option A**: have the tracer watermark factory store the response in
          a small mutable container that callers can read. Pass that container
          into the agent watermark factory. The agent factory's `wait` does **not**
          issue its own request; it waits for the same `rid` to appear on
          `interfaces.agent`.
        - **Option B**: have a single combined factory `make_watermark(...)`
          that returns two `Condition` objects sharing closure state.
    - Recommended: Option A. It keeps each factory focused and uses an explicit
      `WatermarkContext` dataclass with one field, `response`, that the tracer
      watermark sets.
2. `_wait_for_setup_conditions` in `endtoend.py`:
    - Build a `ctx = WatermarkContext()`.
    - `add(make_tracer_watermark(..., context=ctx))`.
    - `add(make_agent_watermark(..., context=ctx))`.
    - Order matters: registration order is the wait order. Tracer first.
3. Unit tests:
    - Agent watermark waits for the `rid` already populated by tracer watermark.
    - Agent watermark with no shared response (tracer watermark unfilled)
      returns False without crashing.

**Acceptance**: `DEFAULT` still passes everywhere from Step 3. The agent
watermark adds < 1s on a successful run because the data has typically already
arrived.

---

### Step 5 — Telemetry message-count barrier + fix PHP heartbeat

**Files**: `utils/wait_conditions.py`, `utils/_context/_scenarios/endtoend.py`,
`tests/test_the_test/test_wait_conditions.py`.

**What to implement**:

1. `make_telemetry_barrier(*, interfaces, min_messages_per_runtime, request_type=None, timeout=...) -> Condition`.
    - Predicate `has_enough_messages_by_runtime()`:
        - Iterate `interfaces.library.get_telemetry_data()`.
        - Group by `runtime_id` from message content.
        - If `request_type` is set, count only messages of that type per runtime;
          else count all messages.
        - Return `True` iff at least one runtime is observed and every observed
          runtime has `>= min_messages_per_runtime`.
    - Short-circuit: if no telemetry data has been observed at all (no
      `app-heartbeat` and no `app-started`) after one cheap check, return True.
      Document this is the Ruby case.
    - Wait pattern: synchronous check → `interfaces.library.wait_for(predicate)`
      → synchronous check.
2. `_wait_for_setup_conditions`:
    - Always register a heartbeat barrier with
      `min_messages_per_runtime=2, request_type="app-heartbeat",
      timeout=context.telemetry_heartbeat_interval * 3 + 1`.
    - Two heartbeats is enough as a setup-time barrier. Tests that need more
      (`test_app_heartbeats_delays` needs 3) register their own additional
      condition in their `setup_*` methods. **Do not** baseline three at the
      scenario level; that bakes test-specific waiting into every scenario.
3. Move `setup_app_heartbeats_delays` into `tests/test_telemetry.py` if it
   does not already live there. It should call
   `wait_conditions.add(wait_conditions.make_telemetry_barrier(...))` with
   `min_messages_per_runtime=3`. Same for `setup_seq_id` if needed.
4. Unit tests cover:
    - Single-runtime, enough messages → True without `wait_for`.
    - Single-runtime, not enough messages, more arrive during `wait_for` → True.
    - No telemetry at all → True (short-circuit).
    - `request_type` filtering counts correctly.

**Acceptance**: PHP `Test_Telemetry::test_app_heartbeats_delays` passes on
`DEFAULT` again. All other libraries still green.

---

### Step 6 — PHP per-worker watermark

**Files**: `utils/wait_conditions.py`, `utils/_weblog.py`,
`utils/interfaces/_library/_core.py` (or wherever `interfaces.library` lives).

**What to implement**:

1. `weblog.get_all_seen_rids() -> list[str]`: returns every `rid` the weblog has
   issued during the setup phase. Implement by appending each issued `rid` to a
   `_seen_rids: list[str]` field on the weblog object. Reset on
   `weblog.reset()` / scenario teardown.
2. `interfaces.library.get_seen_rids() -> set[str]`: returns the set of `rid`s
   that have appeared on any captured span / request on the library interface.
3. `make_php_per_worker_watermark(*, weblog, interfaces, timeout=...) -> Condition`:
    - First check: `set(weblog.get_all_seen_rids()) <= interfaces.library.get_seen_rids()`.
    - If False, `interfaces.library.wait_for(lambda _data: <same predicate>, timeout)`.
    - Final check, return result.
4. In `_wait_for_setup_conditions`, register this **only** when
   `self.library.name == "php"` (and ideally only for `php-fpm` and Apache
   `mod_php` weblog variants). It supplements, does not replace, the regular
   tracer watermark.

**Acceptance**: PHP `DEFAULT` setup converges; matrix run shows no PHP
regressions vs. baseline.

---

### Step 7 — Remote-config message-count barrier

**Files**: `utils/wait_conditions.py`, `utils/_context/_scenarios/endtoend.py`,
`utils/_context/_scenarios/__init__.py` (RC scenarios).

**What to implement**:

1. `make_rc_barrier(*, proxy_state, interfaces, timeout=...) -> Condition | None`.
    - If `proxy_state.mock_remote_config_backend is None`, return `None` and the
      caller filters it out.
    - Predicate: count config requests received from the library on
      `interfaces.library.get_data(path_filters=re.compile(r"^/v\d+\.\d+/config$"))`.
      Threshold is `len(proxy_state.mock_remote_config_backend.MOCKED_RESPONSES) + 2`.
    - Standard "first check / wait_for / final check" pattern.
2. In `_wait_for_setup_conditions`, conditionally register the RC barrier if
   the scenario has a mock RC backend.
3. **Do not** globally tighten `DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS` in this
   PR. If a specific RC scenario takes too long, follow up in a separate PR
   with measurements.
4. Flip `use_wait_conditions=True` on one RC scenario first (recommended:
   `REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES`). After it stays green, flip the
   rest in a follow-up PR.

**Acceptance**: chosen RC scenario passes; setup time noticeably shorter than
the prior fixed `library_interface_timeout=100` on Java (where RC failures
clustered in the original Step 0 failure map).

---

### Step 8 — OTel watermark + flip `OpenTelemetryScenario`

**Files**: `utils/wait_conditions.py`, `utils/_context/_scenarios/endtoend.py`,
`utils/_context/_scenarios/open_telemetry.py` (or wherever OTel scenarios live).

**What to implement**:

1. `make_otel_watermark(*, weblog, interfaces, endpoint="/basic/trace", timeout=...) -> Condition`.
    - Same shape as `make_tracer_watermark`, but:
        - Uses `endpoint="/basic/trace"`.
        - Reads from `interfaces.open_telemetry.get_spans(...)`.
2. In `_wait_for_setup_conditions`, when `self.include_opentelemetry`,
   additionally register the OTel watermark.
3. Flip `use_wait_conditions=True` on `OpenTelemetryScenario` (or whichever
   subclass / instance is the OTel default).
4. `backend_interface_timeout` stays — the OTel collector → backend path
   still relies on it.

**Acceptance**: OTel scenario is green after the flip.

---

### Step 9 — Custom conditions: port profiling and DSM

**Files**: `tests/test_profiling.py`, `tests/integrations/test_dsm.py`,
`utils/wait_conditions.py` (only if a generic helper is worth extracting).

**What to implement**:

1. `tests/test_profiling.py`: in `_common_setup` or in each `setup_library`,
   call `wait_conditions.add(Condition(...))` with a wait function that
   checks for at least one `/profiling/v1/input` request on
   `interfaces.library`. Use the standard wait pattern.
2. `tests/integrations/test_dsm.py`: replace `DsmHelper.wait_for_hashes` with
   `wait_conditions.add(Condition(...))` registered in each test's `setup_*`,
   waiting until the expected DSM hashes appear on `interfaces.agent`.
   - **Optional sub-PR**: refactor DSM tests to read hashes once in `setup_*`
     and store them on `self`, so the test methods do pure assertions. Land
     that refactor as a separate PR if it's noisy.
3. Flip `use_wait_conditions=True` on `PROFILING` and `INTEGRATIONS_DSM`
   scenarios. Confirm green.

**Acceptance**: both scenarios green; matrix run shows no new failures.

---

### Step 10 — Flip `use_wait_conditions=True` as the default

**Files**: `utils/_context/_scenarios/endtoend.py`,
`utils/_context/_scenarios/__init__.py`, `utils/_context/_scenarios/debugger.py`.

**What to implement**:

1. Change `EndToEndScenario.__init__` default: `use_wait_conditions: bool = True`.
2. Remove the per-scenario `use_wait_conditions=True` overrides that became
   redundant.
3. For any scenario that surfaces a regression in matrix runs, leave an
   explicit `use_wait_conditions=False` with an inline `# TODO(<jira>): ...`
   comment.
4. Add the kill-switch env var:
   ```python
   if os.environ.get("SYSTEM_TESTS_WAIT_CONDITIONS") == "0":
       self._use_wait_conditions = False
   ```
   Document it in `docs/internals/end-to-end-life-cycle.md`.

**Acceptance**:

- Matrix run on at least three libraries (recommended: python, java, php — they
  cover the three different "late flush" behaviors found in the original
  Step 0 failure map) shows no new failures vs. the pre-flip baseline.
- Full CI on the merged PR is green.

---

### Step 11 (optional) — Retire the legacy interface waits

Only land if Steps 3–10 stay stable on `main` for at least two weeks.

**Files**: `utils/_context/_scenarios/endtoend.py`,
`utils/interfaces/_core.py`, `utils/interfaces/_library/_core.py`,
`utils/interfaces/_agent/_core.py`, all scenario declarations,
`docs/edit/flushing.md`, `docs/internals/end-to-end-life-cycle.md`.

**What to implement**:

1. Replace `library_interface_timeout` and `agent_interface_timeout` with a
   single `post_setup_timeout` on `EndToEndScenario.__init__`. Keep the union
   of their old values as the default so per-scenario tunings carry over
   directly.
2. `backend_interface_timeout` stays (no replacement).
3. Delete `interfaces.library.wait(timeout)` and `interfaces.agent.wait(timeout)`.
   Keep `interfaces.backend.wait(timeout)`.
4. Delete the per-library timeout table (`endtoend.py:312-327`). Replace with
   per-scenario `post_setup_timeout=` overrides where the table previously
   diverged.
5. Update the two docs files.

**Acceptance**: diff is purely mechanical; matrix run identical to pre-PR.

---

## Risks

| Risk | Mitigation |
| --- | --- |
| A library's trace pipeline is not actually FIFO end-to-end. | Step 10 gates on matrix-run regression. Pin the offending scenario to `use_wait_conditions=False` and investigate. |
| Telemetry `min_messages_per_runtime=2` is wrong for some library. | Short-circuit on "no telemetry observed" (Ruby). Log a warning when the short-circuit fires so silent failures surface. |
| `weblog.post_setup=True` leaks into `responses` and breaks tests. | The `responses` exclusion + caller assertion both have to fail; one is enough to catch misuse. |
| One slow condition starves later ones. | Every condition still runs once with `effective_timeout=0` and reports its failure. Order matters: register dependency producers first. |
| Global registry pollution across scenarios in the same process. | `_wait_for_setup_conditions` calls `wait_conditions.clear()` on entry. Unit tests clear with an autouse fixture. |
| New scenario lands without `use_wait_conditions=True` after Step 10. | Default is `True` post-Step-10, so new scenarios opt in automatically. |

---

## Open follow-ups (not blockers)

- Whether to surface a "post-setup timing report" so we can compare wait
  durations across libraries. Cheap to add later: `wait_conditions.run` already
  knows `start - now` per condition.
- Whether to extend the kill-switch env var into a per-condition disable
  (`SYSTEM_TESTS_WAIT_CONDITIONS=tracer_watermark,agent_watermark`). Only
  worth doing if we hit a flaky condition in production CI.
