## When to Use Decorators vs Manifests

**Always prefer [manifest files](./manifest.md) over decorators.** Manifests can handle test files, classes, AND individual methods.

Use declaration decorators **only** when the condition cannot be expressed in manifests:
- `context.scenario` - Scenario-specific conditions
- `context.agent_version` - Agent version conditions alongside other conditions (conditions on the agent version alone can be expressed in the agent manifest)
- `context.vm_name` - VM-specific conditions
- `context.installed_language_runtime` - Runtime version conditions
- Complex boolean logic combining non-library attributes

If your condition depends only on library name, library version, or weblog variant, use the manifest file instead.

If you need force-skip behavior (e.g., the test is too slow or crashes the scenario), use a manifest entry for the declaration and add a [`@slow` or `@scenario_crash`](#force-skip-decorators) decorator on the test.

## Decorator Types and Behavior

### Declaration decorators

These decorators express **why** a test is deactivated. **Always prefer [manifest files](./manifest.md)** for conditions that only depend on library, version, or weblog.

| Decorator | Behavior | When to Use |
|-----------|----------|-------------|
| `@irrelevant` | Test is **SKIPPED** (not executed) | Feature doesn't apply to this context |
| `@missing_feature` | Test **RUNS**, XFAIL if fails, XPASS if passes | Feature not yet implemented |
| `@bug` | Test **RUNS**, XFAIL if fails, XPASS if passes | Known bug |
| `@flaky` | Test is **SKIPPED** (not executed by default) | Intermittent failures |
| `@incomplete_test_app` | Same as `@missing_feature` | Weblog endpoint not implemented |

### Force-skip decorators

These decorators express **how** a deactivated test should behave. They are placed directly on the test and work in combination with a declaration (from a manifest entry or a declaration decorator). When a test has both a force-skip decorator and a declaration, it is **skipped entirely** instead of running as xfail.

| Decorator | When to Use |
|-----------|-------------|
| `@slow` | Test is too slow to run when it is already known to fail |
| `@scenario_crash` | Test failure would crash the scenario and affect other tests |

Without a declaration, these decorators have no effect: the test runs normally.

#### Why force-skip decorators exist

By default, deactivated tests (via `@bug` or `@missing_feature`) still run as xfail so that system-tests can detect when a fix lands (xpass / easy win). However, running a deactivated test is not always desirable:

- **Slow tests**: running a test that takes minutes just to confirm it still fails wastes CI time.
- **Crash-prone tests**: a failing test that brings down the whole scenario prevents other tests from running.

In these cases, add `@slow` or `@scenario_crash` on the test. The test will be skipped for as long as it has a declaration, and will automatically start running again once the declaration is removed (i.e., the feature is implemented or the bug is fixed).

#### Example

```python
from utils import slow, scenario_crash, missing_feature

@slow
@missing_feature(condition=True, reason="Feature not implemented yet")
def test_heavy_computation(self):
    """This test is slow and not yet supported -- skip entirely."""
    ...

@scenario_crash
@missing_feature(condition=True, reason="Crashes the agent")
def test_crash_prone(self):
    """This test crashes the scenario when it fails -- skip entirely."""
    ...
```

These decorators replace the `force_skip=True` parameter on declaration decorators, which is being deprecated in favor of manifests. Since manifests cannot carry a `force_skip` flag, `@slow` and `@scenario_crash` let you decouple the declaration (in the manifest) from the force-skip behavior (on the test).

## Declaration Decorator Parameters

The declaration decorators take several arguments:

* `condition`: Boolean expression. As it's the first argument, you can omit the argument name
* `library`: Target library with optional version, e.g. `library="java@1.2.4"`. See [versions.md](./versions.md) for more details on semantic versioning
* `weblog_variant`: Skip the test for a specific weblog
* `reason`: Explanation for the skip. Always include a JIRA ticket for `@bug` and `@flaky`
* `force_skip`: **(Deprecated, prefer `@slow` or `@scenario_crash`)** Set to `True` to completely prevent test execution

### Version Format in Decorators

When using version comparisons with `context.library`, always use the `library@version` format:

```python
# CORRECT
@missing_feature(context.library < "python@2.5.0", reason="...")

# WRONG - missing library specifier
@missing_feature(context.library < "2.5.0", reason="...")
```

## Example

```python
from utils import irrelevant, incomplete_test_app, bug, missing_feature, slow, scenario_crash


@irrelevant(library="nodejs")
class Test_AwesomeFeature:
    """ Short description of Awesome feature """

    @bug(weblog_variant="echo", reason="JIRA-666")
    def test_basic(self)
        assert P==NP

    @missing_feature(library="java@1.2.4", reason="still an hypothesis")
    def test_extended(self)
        assert riemann.zetas.zeros.real == 0.5

    @missing_feature(reason="Maybe too soon")
    def test_full(self)
        assert 42

    @incomplete_test_app(library="python", "trace/span/start endpoint does not exist")
    def test_span_creation(self):
        assert 68
```
