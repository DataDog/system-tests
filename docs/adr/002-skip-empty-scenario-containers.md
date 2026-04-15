# ADR-002: Skip Container Startup for Empty Scenarios

## Metadata

- **Status**: Accepted
- **Date**: 2026-04-15
- **Tags**: `scenarios`, `containers`, `ci`, `framework`
- **Affected areas**: end-to-end scenarios, container lifecycle, pytest collection
- **Authors**: nccatoni

## Context

In system-tests CI, a scenario is "empty" when every collected test is deselected
(marked `missing_feature`, `irrelevant`, `bug`, or `skip`) for a given library/weblog
combination. The `--skip-empty-scenario` flag (used in `ci.yml`) exits gracefully
instead of failing, but Docker infrastructure was still started and torn down for every
empty scenario.

Detailed timing analysis showed this wasted roughly **17 hours of compute per full CI
run** (~38% of scenario invocations are empty), with PHP alone accounting for 8.8h. See
[empty-scenario-overhead-analysis.md](./empty-scenario-overhead-analysis.md) for the
full breakdown.

The root cause was the pytest hook order: `pytest_sessionstart` executes warmups
(which start containers) **before** collection and deselection happen, so there was no
point in the lifecycle where we knew "zero tests will run" before containers started.

## Decision

Move container startup from `pytest_sessionstart` (pre-collection) to a new
post-collection warmup phase that runs inside `pytest_collection_finish`. Combined with
reading library and agent versions from Docker image labels (rather than from running
containers), this enables:

1. **Version info in test context** — `Agent:`, `Library:`, `Weblog variant:` lines
   appear in the `=== test context ===` section even when containers never start.
2. **Zero-cost empty scenarios** — `pytest_collection_finish` returns early when
   `len(session.items) == 0`, so containers are never created for empty scenarios.

The implementation uses a three-way branch in `EndToEndScenario.configure()`:

- **Defer path** (both versions known from image labels, not replay): container startup
  and all dependent steps move to `post_collection_warmups`. Selected in the fast path.
- **Fallback path** (library version from label, agent version unknown): containers
  still start in `pytest_sessionstart`; agent version read from healthcheck.
- **Legacy path** (no label data): original behaviour, both versions read from running
  containers.

## Consequences

### Positive

- Empty scenarios complete in ~2.5s instead of 20-40s.
- ~17h of CI compute saved per full CI run.
- The `=== test context ===` block is populated before "test session starts" in all
  paths, making logs consistent and easier to grep.

### Negative

- For the defer path, `Weblog system:` appears after `=== test session starts ===`
  rather than in `=== test context ===`. This is a minor cosmetic change.
- Scenarios where the weblog image was built without the `system-tests-library-version`
  label (older images, custom builds) fall back to the legacy path and do not get the
  speedup.

### Risks

- Edge cases not fully tested at time of writing: replay mode, `include_agent=False`
  scenarios, scenarios with buddy containers, OTel scenarios. Code paths exist for all
  of these (they hit the fallback or legacy path), but integration testing is pending.

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-15 | Created ADR, implementation accepted | Feature functionally complete; delivers measurable CI savings. Edge-case testing deferred to follow-up. |

## Implementation Status

### Implemented

| Component | Location | Status |
|-----------|----------|--------|
| Library version label in image | `utils/build/build.sh:296` | Done |
| Write version in install scripts | `utils/build/docker/*/install_ddtrace.sh` | Done |
| `WeblogContainer.configure()` reads label | `utils/_context/containers.py:1022` | Done |
| `AgentContainer.configure()` reads label | `utils/_context/containers.py:800` | Done |
| `post_collection_warmups` + `execute_post_collection_warmups()` | `utils/_context/_scenarios/core.py:131` | Done |
| Three-way branch + `_defer_container_startup()` | `utils/_context/_scenarios/endtoend.py:337` | Done |
| Early return in `pytest_collection_finish` | `conftest.py:411` | Done |

### Not Yet Implemented

| Component | Notes |
|-----------|-------|
| Integration tests for edge cases | replay mode, buddy containers, OTel, `include_agent=False` |

## References

- [empty-scenario-overhead-analysis.md](./empty-scenario-overhead-analysis.md) — timing data and root-cause analysis
- `conftest.py` — `pytest_collection_finish` hook
- `utils/_context/_scenarios/core.py` — `Scenario.post_collection_warmups`
- `utils/_context/_scenarios/endtoend.py` — `EndToEndScenario.configure`, `_defer_container_startup`
- `utils/_context/containers.py` — `AgentContainer.configure`, `WeblogContainer.configure`
- `docs/execute/skip-empty-scenario.md` — `--skip-empty-scenario` documentation
