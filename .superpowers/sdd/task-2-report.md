# Task 2 Report: Extract `start_agent`/`stop_agent` + add `rebind_request`

## Status

DONE_WITH_CONCERNS

## Commit hash

`d63db0ea2`

## Files Modified

- `utils/docker_fixtures/_test_agent.py` — extracted `start_agent`, added `rebind_request`, refactored `get_test_agent_api` to delegate
- `tests/test_the_test/test_start_stop_agent.py` — new Docker-backed smoke test (created)

---

## Implementation Notes

### Spec deviation: `None`-safe `request.cls`

The brief's `start_agent` body uses `request.cls.__name__` verbatim in the log path. When the smoke test (a module-level function, not a class method) was run, `request.cls` was `None`, causing `AttributeError`. The fix was to use `cls_name = request.cls.__name__ if request.cls else "NoClass"` in:
- `start_agent` log path
- `get_test_agent_api` teardown log path
- `TestAgentAPI.__init__` log path
- `TestAgentAPI.rebind_request` log path

This is defensive hygiene consistent with how `_request_token` already handles `None` (`request.cls.__name__ if request.cls else ""`). The normal production path (parametric test functions are always inside a class) is unaffected.

### `Callable` import

The existing `from collections.abc import Generator` was replaced with `from collections.abc import Generator, Callable` as specified.

---

## Verification

### Step 2 — Confirm test fails before implementation

Direct check (pytest with root conftest causes `TypeError` unrelated to our code):

```
python -c "from utils.docker_fixtures._test_agent import TestAgentFactory; f = TestAgentFactory(''); print(hasattr(f, 'start_agent'))"
# Output: False  (confirmed AttributeError would follow)
```

The root conftest has a pre-existing `TypeError: 'bool' object is not iterable` in `_item_must_pass` that prevents normal pytest collection with the full conftest. Running with `--noconftest` bypasses it.

### Step 5 — Docker smoke test (after implementation)

Command:
```
DOCKER_SMOKE=1 python -m pytest tests/test_the_test/test_start_stop_agent.py -v --noconftest
```

Output:
```
============================= test session starts ==============================
collecting ... collected 1 item

tests/test_the_test/test_start_stop_agent.py::test_start_agent_then_stop PASSED [100%]

============================== 1 passed in 2.95s ===============================
```

### Step 6 — Parametric regression test

Command:
```
TEST_LIBRARY=php ./run.sh PARAMETRIC tests/parametric/test_otel_span_methods.py -k test_otel_get_span_context --skip-parametric-build
```

Note: `--skip-parametric-build` was required because the `binaries/` directory contains symlinks to paths outside the Docker build context (pointing to `~/dd/system-tests/binaries/`), so `docker build` can't follow them in the worktree. The pre-built `php-test-client:latest` image was used. This is a pre-existing environment constraint.

Output:
```
Skipping parametric build (image already exists, --skip-parametric-build or SKIP_PARAMETRIC_BUILD)
================================= test context =================================
Scenario: PARAMETRIC
Logs folder: ./logs_parametric
Library: php@1.21.0
============================= test session starts ==============================
gw0 [1] / gw1 [1] / ... / gw15 [1]

. [100%]
============================== 1 passed in 10.78s ==============================
```

---

---

## Review-Finding Fixes (post-commit d63db0ea2)

### Fixes applied

1. **CRITICAL — container leak on readiness timeout**: The `for...else` branch in `start_agent` now calls `cm.__exit__(None, None, None)` inside a `try/finally` (with `log_file.close()` in the `finally`) before `pytest.fail(...)`, ensuring the container is stopped even when it never becomes ready.

2. **IMPORTANT — log path duplication**: Extracted `_agent_log_path(host_log_folder, request)` as a module-level helper. Both `start_agent` and the `get_test_agent_api` `finally` block now call this helper instead of inline construction. The `cls_name` local variable was removed from both sites.

3. **MINOR (lint) — F541 f-string**: Changed `f"8126/tcp"` → `"8126/tcp"` in the `ports` dict.

### Verification

#### Docker smoke test

Command:
```
DOCKER_SMOKE=1 python -m pytest tests/test_the_test/test_start_stop_agent.py -v --noconftest
```

Output:
```
============================= test session starts ==============================
collecting ... collected 1 item

tests/test_the_test/test_start_stop_agent.py::test_start_agent_then_stop PASSED [100%]

--------------------------------- JSON report ----------------------------------
report saved to: .report.json
============================== 1 passed in 2.98s ==============================
```

#### Parametric regression

Command:
```
TEST_LIBRARY=php ./run.sh PARAMETRIC tests/parametric/test_otel_span_methods.py -k test_otel_get_span_context --skip-parametric-build
```

Output:
```
Skipping parametric build (image already exists, --skip-parametric-build or SKIP_PARAMETRIC_BUILD)
================================= test context =================================
Scenario: PARAMETRIC
Logs folder: ./logs_parametric
Library: php@1.21.0
============================= test session starts ==============================
gw0 [1] / gw1 [1] / ... / gw15 [1]

. [100%]
============================== 1 passed in 10.29s ==============================
```

---

## Self-review Notes

1. **DRY requirement satisfied**: `get_test_agent_api` is now a thin wrapper that calls `start_agent` for lifecycle and only handles snapshot marks and report-section teardown. The create-and-wait logic exists in exactly one place.

2. **`rebind_request` stores `_host_log_folder`**: `self._host_log_folder = host_log_folder` is added right after `self.network = network` in `TestAgentAPI.__init__`, enabling the rebind method to reconstruct the log path.

3. **`_stop()` closure**: The `_stop()` callable in `start_agent` calls `cm.__exit__(None, None, None)` in a `try/finally` with `log_file.close()` in the `finally` block, ensuring the log file is always closed even if container stop raises.

4. **`container_port` variable**: The original code had a local `container_port = 8126` variable. The refactored `start_agent` uses the literal `8126` directly in the port mapping and `TestAgentAPI` constructor, which is equivalent and avoids the now-unused variable.

5. **Smoke test `--noconftest` note**: The smoke test as written requires `--noconftest` to run cleanly in the worktree due to a pre-existing conftest bug (`TypeError: 'bool' object is not iterable` in `_item_must_pass`). In CI, the parametric suite uses its own conftest path and does not trigger this bug.
