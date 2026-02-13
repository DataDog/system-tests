## When to Use Decorators vs Manifests

**Always prefer [manifest files](./manifest.md) over decorators.** Manifests can handle test files, classes, AND individual methods.

Use decorators **only** when the condition cannot be expressed in manifests:
- `context.scenario` - Scenario-specific conditions
- `context.agent_version` - Agent version conditions alongside other conditions (conditions on the agent version alone can be expressed in the agent manifest)
- `context.vm_name` - VM-specific conditions
- `context.installed_language_runtime` - Runtime version conditions
- Complex boolean logic combining non-library attributes
- `force_skip=True` requirement

If your condition depends only on library name, library version, or weblog variant, use the manifest file instead.

## Decorator Types and Behavior

| Decorator | Behavior | When to Use |
|-----------|----------|-------------|
| `@irrelevant` | Test is **SKIPPED** (not executed) | Feature doesn't apply to this context |
| `@missing_feature` | Test **RUNS**, XFAIL if fails, XPASS if passes | Feature not yet implemented |
| `@bug` | Test **RUNS**, XFAIL if fails, XPASS if passes | Known bug |
| `@flaky` | Test is **SKIPPED** (not executed by default) | Intermittent failures |
| `@incomplete_test_app` | Same as `@missing_feature` | Weblog endpoint not implemented |

## Decorator Parameters

The decorators take several arguments:

* `condition`: Boolean expression. As it's the first argument, you can omit the argument name
* `library`: Target library with optional version, e.g. `library="java@1.2.4"`. See [versions.md](./versions.md) for more details on semantic versioning
* `weblog_variant`: Skip the test for a specific weblog
* `reason`: Explanation for the skip. Always include a JIRA ticket for `@bug` and `@flaky`
* `force_skip`: Set to `True` to completely prevent test execution (use sparingly, for cases where the test would crash the app)

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
from utils import irrelevant, incomplete_test_app, bug, missing_feature


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
