# Exercise 3: Call a New Weblog Endpoint (It Will Fail)

## Background

Both existing tests call the root endpoint `GET /`, which is part of the shared weblog specification and already implemented everywhere. Now you'll write a test **against an endpoint that does not exist yet**, and watch it fail before touching any weblog code.

`weblog.get(...)` never raises just because an endpoint is missing — it returns a normal response object, whose `status_code` will simply be `404`. All documented endpoints live in `docs/understand/weblogs/end-to-end_weblog.md`; if it's not listed there, assume it doesn't exist.

## Goal

Add a **third** test method, `test_new_endpoint`, to `Test_Labs` in `tests/test_labs.py`. It calls **`/my_labs_endpoint`** and asserts the response status code is `200` and the body is exactly `Labs!`.

Do not implement the endpoint yet — that's Exercise 4. For now, confirm the test fails.

## Hints

1. Same pattern as the other two: a `setup_*`/`test_*` pair.
2. `weblog.get("/my_labs_endpoint")` — expect a `404` for now.
3. Leave `test_root_ok` and `test_root_wrong` (and its manifest entry from Exercise 2) untouched.

## Expected Result

```python
from utils import weblog, features


@features.base_service
class Test_Labs:
    """Tests: pass, fail-on-purpose (deactivated via manifest), and a new endpoint."""

    def setup_root_ok(self):
        self.r = weblog.get("/")

    def test_root_ok(self):
        assert self.r.status_code == 200, f"Expected 200, got {self.r.status_code}"

    def setup_root_wrong(self):
        self.r = weblog.get("/")

    def test_root_wrong(self):
        # Intentionally wrong expectation, deactivated for all libraries via manifests/nodejs.yml (and friends)
        assert self.r.status_code == 999, f"Expected 999, got {self.r.status_code}"

    def setup_new_endpoint(self):
        self.r_new = weblog.get("/my_labs_endpoint")

    def test_new_endpoint(self):
        assert self.r_new.status_code == 200, f"Expected 200, got {self.r_new.status_code}"
        assert self.r_new.text == "Labs!", f"Expected 'Labs!', got {self.r_new.text!r}"
```

## Verification

```bash
./run.sh tests/test_labs.py
```

Now answer the following questions:

- Did `test_new_endpoint` fail? On which assertion, and with what status code?
- Is `test_root_wrong` still correctly skipped by the manifest entry from Exercise 2?

> **Note:** This failure is expected at this stage — it signals a missing weblog feature, not a tracer bug. That's exactly why `incomplete_test_app` exists as a marker (you'll use that reasoning again in the bonus questions).

## Bonus / Follow-up Questions

1. What's the practical difference between this failure and the one from Exercise 1 (`test_root_wrong`)? Which marker (`irrelevant` vs `incomplete_test_app`) would each deserve if you had to deactivate them?
2. If you ran this same test right now against a Java or Python weblog, would anything change?
3. Where must `/my_labs_endpoint` be documented before it can be considered part of the shared weblog API?
