# Exercise 5: Create a New Scenario

## Background

`Test_Training4` has lived in `DEFAULT` since Exercise 1. That was the right way to start, but `DEFAULT` is the main end-to-end suite — it's not necessarily where a test with its own environment requirements should stay forever.

A scenario is declared as an attribute of the `_Scenarios` class in `utils/_context/_scenarios/__init__.py`. For this exercise, use the plain **`EndToEndScenario`** class (the same base class used for a generic end-to-end scenario — no need for a more specialized subclass here). A common customization is passing environment variables through `weblog_env`; in Datadog, the service name is controlled by `DD_SERVICE`.

Remember from Exercise 1: **a test class can belong to more than one scenario at once** — just stack the decorators. This exercise is a chance to actually do that, instead of just moving the class from one scenario to another.

## Goal

1. Create a new end-to-end scenario named **`MY_TRAINING4_SCENARIO`** that launches the weblog with service name **`TRAINING4_SERVICE`** (via `DD_SERVICE`).
2. Keep `Test_Training4` running in `DEFAULT` **and** make it also run in `MY_TRAINING4_SCENARIO`, by decorating the class with **both** `@scenarios.default` and `@scenarios.my_training4_scenario`.

## Hints

1. Check first whether an existing scenario already sets `DD_SERVICE=TRAINING4_SERVICE` — it won't (this is a training-only value), but always check before creating a new one.
2. The scenario must be an `EndToEndScenario` instance, declared as an attribute inside `_Scenarios`, with a meaningful `doc` string.
3. Once you add `@scenarios.default` explicitly, the class carries a decorator — see the bonus of Exercise 1 about how that changes which `./run.sh` command finds it.
4. Stacking `@scenarios.default` and `@scenarios.my_training4_scenario` on the same class makes it run **twice** — once per scenario — each time against a freshly started environment.

## Expected Result

In `utils/_context/_scenarios/__init__.py`:

```python
my_training4_scenario = EndToEndScenario(
    "MY_TRAINING4_SCENARIO",
    weblog_env={"DD_SERVICE": "TRAINING4_SERVICE"},
    doc="End to end scenario running the weblog with a custom service name (DD_SERVICE=TRAINING4_SERVICE)",
)
```

In `tests/test_training4.py`:

```python
from utils import weblog, features, scenarios


@features.base_service
@scenarios.default
@scenarios.my_training4_scenario
class Test_Training4:
    """Tests: pass, fail-on-purpose (deactivated via manifest), and a new endpoint. Runs under DEFAULT and MY_TRAINING4_SCENARIO."""

    def setup_root_ok(self):
        self.r = weblog.get("/")

    def test_root_ok(self):
        assert self.r.status_code == 200, f"Expected 200, got {self.r.status_code}"

    def setup_root_wrong(self):
        self.r = weblog.get("/")

    def test_root_wrong(self):
        assert self.r.status_code == 999, f"Expected 999, got {self.r.status_code}"

    def setup_new_endpoint(self):
        self.r_new = weblog.get("/my_training4_endpoint")

    def test_new_endpoint(self):
        assert self.r_new.status_code == 200, f"Expected 200, got {self.r_new.status_code}"
        assert self.r_new.text == "Training4!", f"Expected 'Training4!', got {self.r_new.text!r}"
```

You do not need to change the manifest entry from Exercise 2 — manifests key off the test node ID (`file::Class::method`), not the scenario.

## Verification

```bash
# Runs once against DEFAULT...
./run.sh DEFAULT tests/test_training4.py

# ...and once against your new scenario
./run.sh MY_TRAINING4_SCENARIO tests/test_training4.py

# Bare "no scenario" run: does this still find the class, now that it has explicit decorators?
./run.sh tests/test_training4.py
```

Now answer the following questions:

- Did both scenario runs execute `test_root_ok`, skip `test_root_wrong`, and pass `test_new_endpoint`?
- What did the third command do, and why? (Compare with the bonus question from Exercise 1.)
- Is `DD_SERVICE=TRAINING4_SERVICE` actually exercised by any assertion right now, or only by the environment?

## Bonus / Follow-up Questions

1. What additional step is required to make `MY_TRAINING4_SCENARIO` run in CI? (Hint: GitHub workflow + `workflow_data.py`.)
2. How would you extend `test_root_ok` to assert on the custom service name using `interfaces.library.get_root_span(request=self.r)` and `span["service"]`? Would that assertion make sense under `DEFAULT` too, or only under `MY_TRAINING4_SCENARIO`?
3. What's the cost of running the same test class under two scenarios instead of one? (Think about total run time and how many times the weblog gets rebuilt/restarted.)
4. Give a real (non-training) example from this repository where stacking two or more `@scenarios.*` decorators on the same class would make sense.
