# Exercise 1: Write Two Tests in an Existing Scenario

## Background

In system-tests, tests live under `tests/` as regular pytest classes. A test class is linked to a **feature** with `@features.<feature_name>` (mandatory), and, optionally, to one or more **scenarios** with `@scenarios.<scenario_name>`.

If a test class carries **no** `@scenarios` decorator, it belongs to the **`DEFAULT`** scenario. `DEFAULT` already starts a weblog, a Datadog agent, and a proxy — you don't need to create anything to write your first test.

> **A test class is not limited to a single scenario.** You can stack more than one `@scenarios.*` decorator on the same class, and it will run once per scenario listed. You'll see this in practice in Exercise 5.

Reminder of the end-to-end test lifecycle:

1. `setup_*` runs first, while containers are alive, and sends traffic to the weblog via the `weblog` object.
2. Traces/telemetry are intercepted and stored by the validation interfaces.
3. Containers shut down.
4. `test_*` validates either the raw HTTP response or the captured data (`interfaces.library`, `interfaces.agent`, ...).

The root endpoint `GET /` already exists on every end-to-end weblog and returns HTTP `200` (see `docs/understand/weblogs/end-to-end_weblog.md`).

This whole lab series uses the **Node.js Express weblog**. Build it once before running anything, so `DEFAULT` doesn't fall back to whichever weblog you last built:

```bash
./build.sh nodejs -w express4
```

## Goal

Create **one** test class with **two test methods** in a new file:

```
tests/test_labs.py
```

1. `test_root_ok` — call `GET /` and assert `status_code == 200`. Must **pass**.
2. `test_root_wrong` — call `GET /` and assert `status_code == 999`. Must **fail on purpose**.

Do **not** add any `@scenarios` decorator: leave the class implicit, so it belongs to `DEFAULT` by default.

## Hints

1. Pick a real, meaningful feature decorator, e.g. `@features.base_service` — never leave a test undeclared just because it's a training exercise.
2. Each `setup_*` method must match a `test_*` method with the same suffix.
3. Store the response on `self` (e.g. `self.r`) in `setup_*`, then assert on it in `test_*`.

## Expected Result

```python
from utils import weblog, features


@features.base_service
class Test_Labs:
    """Two simple tests: one passes, one fails on purpose."""

    def setup_root_ok(self):
        self.r = weblog.get("/")

    def test_root_ok(self):
        assert self.r.status_code == 200, f"Expected 200, got {self.r.status_code}"

    def setup_root_wrong(self):
        self.r = weblog.get("/")

    def test_root_wrong(self):
        # Intentionally wrong expectation, to observe a failing test report
        assert self.r.status_code == 999, f"Expected 999, got {self.r.status_code}"
```

## Verification

There are several valid ways to run this file — they are **not** equivalent, so it's worth comparing them. Make sure you built the Node.js weblog first (see Background), or `DEFAULT` will start whatever weblog you last built:

```bash
# 1) No scenario name, scoped to the file.
#    Since the class has no @scenarios decorator, it belongs to DEFAULT,
#    and this runs ONLY the 2 tests in this file. Fast, safe.
./run.sh tests/test_labs.py

# 2) Scenario name + file, explicit but same result as (1) here,
#    because "no decorator" and "@scenarios.default" are equivalent.
./run.sh DEFAULT tests/test_labs.py

# 3) Scenario name, no file.
#    This runs the ENTIRE DEFAULT suite (hundreds of tests), not just yours.
./run.sh DEFAULT

# 4) DANGER: no arguments at all -> same as (3), the whole default suite.
./run.sh
```

Use option (1) or (2) while iterating on this lab. Now answer:

- How many tests ran with option (1)? Which one passed, which one failed?
- What happens if you accidentally run option (3) or (4) instead?

## Bonus / Follow-up Questions

1. What would change if you added `@scenarios.default` explicitly to the class? Would option (1) still work the same way?
2. Why does `setup_*` send the request instead of `test_*`?
3. How would you run only `test_root_ok` and not `test_root_wrong`? (Hint: pytest nodeid `file::Class::method`.)
