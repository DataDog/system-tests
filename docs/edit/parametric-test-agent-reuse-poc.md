# POC: parametric test-agent reuse

## Why

The parametric scenario creates a fresh Docker network + test-agent + client
container per test (16 xdist workers x ~440 tests). On the shared docker-in-docker
microVM runners this churn intermittently stalls container/network setup, so a
test-agent occasionally fails to make a just-sent trace queryable within the
tracer's ~3 s receipt poll -> `Number (1) of traces not available, got 0`.

## What this changes

- One test-agent + one Docker network per xdist worker, reused across tests,
  reset with `TestAgentAPI.clear()` (`/test/session/clear`) before each test.
- The library client container is unchanged: it is still created fresh per test
  and derives its network and agent URL from the `test_agent` object it is handed.
  Per-test container operations therefore drop from 3 to 1 for default-env tests
  (agent + network + client -> client only), not a uniform 98% cut in all containers.

## Scope / fallback

Pooling is enabled only for **non-snapshot tests with the default `agent_env == {}`**,
which covers roughly 94% of parametric tests. Two categories fall back to the
existing fresh-per-test path:

1. **Snapshot-marked tests** (`pytest.mark.snapshot`) -- these compare recorded
   agent output and need a clean agent on every run.
2. **Tests with a non-default `agent_env`** -- the pooled agent persists for the
   whole worker session on a worker-keyed host port. Allowing a second pooled
   agent with a different environment, or colliding with a fresh-path agent on
   the same worker, would hit "port already allocated". Keeping at most one
   pooled agent per worker avoids that collision.

To pool non-default-env tests in the future, allocate host ports per
`(worker, env)` instead of per worker.

## Measured results

Benchmark file: `tests/parametric/test_otel_span_methods.py`, single worker.

| Metric | Before | After |
|--------|--------|-------|
| Agent+network create/destroy cycles | 118 | 2 |
| Reduction | -- | ~98% |
| Tests driving the single pooled agent | -- | 59 |
| Per-test container ops (default-env tests) | 3 | 1 |

Stability: 3 consecutive full-file runs each produced 57 passed / 2 skipped /
2 xfailed with no cross-test state leakage detected.

## Operational note

The `REUSE-POC agent container created:` count line is emitted via
`logger.stdout` and lands in `logs_parametric/tests.log` (not the tee'd console
stdout). To measure agent creation counts in CI, grep that file:

```
grep "REUSE-POC agent container created" logs_parametric/tests.log | wc -l
```

## Risks to weigh before adopting

- **State leakage** if `clear()` is ever incomplete. `TestAgentAPI.clear()`
  (`/test/session/clear`) covers traces, telemetry, RC, OTLP, and sessions;
  verified for the trace case in this POC. Extend the leakage check per data
  type before rolling out to all tracers.
- **In-flight data**: a late trace from test N arriving after test N+1's
  `clear()` could leak. Hardening path: per-test agent session tokens (requires
  the client to send `X-Datadog-Test-Session-Token`).
- **Agent container log spans the worker session**, not per-test. Per-test API
  interactions are re-pointed via `rebind_request`; the raw container log is
  shared. Acceptable for a POC; revisit if per-test log isolation is needed.
- **Shared across 9 tracers** -- roll out behind a flag / one language at a time.

## Hardening path summary

1. Extend leakage checks to telemetry, RC, OTLP, and session data.
2. Add per-test session tokens (`X-Datadog-Test-Session-Token`) to guard
   against in-flight-data leakage.
3. Allocate ports per `(worker, env)` to enable pooling of non-default-env tests.
4. Gate the feature behind a flag and roll out one tracer language at a time.
