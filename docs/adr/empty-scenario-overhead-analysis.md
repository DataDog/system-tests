# Empty Scenario Overhead Analysis

## Context

In system-tests CI, scenarios are "empty" when all their collected tests are marked as
`missing_feature`, `irrelevant`, `bug` (xfail), or `skip` for a given library. The
`skip_empty_scenarios` flag (enabled in `ci.yml`) detects this and exits gracefully
instead of failing. However, Docker infrastructure is still started and torn down for
each empty scenario, wasting compute time.

## Root cause: containers start before empty detection

The pytest hook order in the scenario lifecycle means containers start **before** the
empty check runs:

```
1. pytest_configure       → scenario.configure() adds _start_containers to warmups
2. pytest_sessionstart    → executes warmups → CONTAINERS START (20-40s overhead)
3. pytest_collection      → tests collected
4. collection_modifyitems → empty scenario detected, all tests deselected
5. pytest_sessionfinish   → containers torn down, exit code changed to OK
```

Every empty scenario pays the full Docker infrastructure cost (container start +
health check + teardown) even though zero tests run.

## Estimated time savings if empty scenarios had 0 cost

Analysis based on `utils/scripts/ci_orchestrators/time-stats.json`, using per-library
infrastructure overhead thresholds to identify likely-empty scenario runs.

| Library    | Threshold | Total runs | Empty runs | % Empty | Time wasted | Per-job impact |
| ---------- | --------- | ---------- | ---------- | ------- | ----------- | -------------- |
| **PHP**    | <40s      | 1561       | ~879       | 56%     | **8.8h**    | ~21 min/job    |
| **Ruby**   | <30s      | 1346       | ~612       | 45%     | **4.5h**    | ~1.5 min/job   |
| **Golang** | <28s      | 396        | ~205       | 52%     | **1.4h**    | ~14 min/job    |
| **Python** | <35s      | 454        | ~141       | 31%     | **1.3h**    | ~1.6 min/job   |
| **Nodejs** | <30s      | 330        | ~138       | 42%     | **1.0h**    | ~2.5 min/job   |
| **Java**   | <40s      | 975        | ~16        | 1.6%    | **0.1h**    | negligible     |
| **Dotnet** | <40s      | 131        | ~4         | 3.1%    | negligible  | negligible     |
| **TOTAL**  |           | **5194**   | **~1995**  | **38%** | **~17h**    |                |

### Key takeaways

- **~17 hours of compute time per full CI run** could be saved (~17% of ~100h total
  end-to-end compute).
- **~14-21 minutes wall-clock** on the critical path (PHP and Golang jobs).
- **PHP is the biggest offender**: 24 weblogs x 35 empty scenarios x 36s each = 8.8
  hours wasted on container start/stop for nothing.

## Potential fix

Move the empty-scenario check **before** `pytest_sessionstart`, so containers never
start for empty scenarios. A pre-collection manifest check could determine if a
scenario has any eligible tests before spinning up infrastructure.

## References

- `conftest.py` — `pytest_collection_modifyitems` and `_item_must_pass`
- `utils/_context/_scenarios/core.py` — `pytest_sessionstart` warmup execution
- `utils/_context/_scenarios/endtoend.py` — `_start_containers` in warmups
- `utils/scripts/ci_orchestrators/time-stats.json` — scenario execution time data
- `docs/execute/skip-empty-scenario.md` — `--skip-empty-scenario` documentation
