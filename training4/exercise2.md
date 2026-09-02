# Exercise 2: Activate / Deactivate a Test — Manifest First

## Background

`test_root_wrong` fails on every run. Leaving a known-failing test enabled makes the suite noisy and hides real regressions, so it needs to be deactivated.

System-tests gives you two mechanisms:

- **Manifests** (`manifests/<library>.yml`) — the **preferred, default choice** whenever the condition depends only on the library name, library version, weblog variant, or agent version. See `docs/edit/manifest.md`.
- **Decorators** (`@bug`, `@missing_feature`, `@irrelevant`, `@flaky`, ...) — only used when the condition needs something a manifest cannot express (e.g. `context.scenario`, `context.vm_name`, or another runtime attribute).

**Rule of thumb: always reach for the manifest first.** Only fall back to a decorator when the condition genuinely cannot be expressed as a per-library/version/weblog/agent rule.

Available manifest markers: `bug`, `flaky`, `missing_feature`, `irrelevant`, `incomplete_test_app`. Here the test itself is intentionally wrong (not a tracer bug, not a missing feature), so `irrelevant` is the right marker.

Tests are addressed by their **node ID**, e.g. `tests/test_training4.py::Test_Training4::test_root_wrong`.

## Goal

Deactivate **only** `test_root_wrong` using a **manifest** entry, leaving `test_root_ok` untouched. You're working with the Java Spring Boot weblog, so add the entry to `manifests/java.yml`.

## Hints

1. This condition depends only on the library → **manifest**, not a decorator.
2. Target the **method**, not the whole class, so `test_root_ok` stays enabled: `tests/test_training4.py::Test_Training4::test_root_wrong`.
3. Use the `irrelevant` marker with a short reason in parentheses.
4. After editing, **always run `./format.sh`** — it validates syntax and re-sorts entries alphabetically.

## Expected Result (primary solution — manifest)

In `manifests/java.yml`:

```yaml
  tests/test_training4.py::Test_Training4::test_root_wrong: irrelevant (intentional wrong assertion used in the training lab)
```

`test_root_ok` has no manifest entry, so it stays enabled.

```bash
./format.sh
```

## Verification

```bash
./run.sh tests/test_training4.py
```

Now answer the following questions:

- How many tests were **executed** this time, and how many were **skipped**?
- What status does `test_root_wrong` report now?
- Did `test_root_ok` keep passing?

> **Note:** the manifest entry doesn't delete the test — it documents *why* it's off, and for whom. Anyone reading `manifests/java.yml` can see the reason without opening the test file.

## Secondary note — the decorator alternative

For comparison only (this is **not** what you should have used here, since the manifest already covers it), the same effect *could* be achieved with a decorator directly on the method:

```python
from utils import weblog, features, irrelevant


@features.base_service
class Test_Training4:
    def setup_root_ok(self):
        self.r = weblog.get("/")

    def test_root_ok(self):
        assert self.r.status_code == 200, f"Expected 200, got {self.r.status_code}"

    def setup_root_wrong(self):
        self.r = weblog.get("/")

    @irrelevant(reason="Training exercise: intentional wrong assertion")
    def test_root_wrong(self):
        assert self.r.status_code == 999, f"Expected 999, got {self.r.status_code}"
```

Keep the **manifest** version as your actual solution for this exercise; only use the decorator form when the condition truly cannot be expressed in a manifest (e.g. it depends on `context.scenario` or `context.vm_name`).

## Bonus / Follow-up Questions

1. Why is the manifest the preferred mechanism here, and what concrete condition would force you into a decorator instead?
2. What would happen if you mistakenly put the `irrelevant` entry on `Test_Training4` (the whole class) instead of just `test_root_wrong`?
3. The `-F` flag forces a disabled test to run anyway (see `docs/execute/run.md`). Try `./run.sh DEFAULT -F tests/test_training4.py::Test_Training4::test_root_wrong`. What happens?
4. How would you re-enable `test_root_wrong` later, and what else would you need to change so it would actually pass?
