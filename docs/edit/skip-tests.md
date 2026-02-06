## When to Use Decorators vs Manifests

**Always prefer [manifest files](./manifest.md) over decorators.** Manifests can handle test files, classes, AND individual methods.

Use decorators **only** when the condition cannot be expressed in manifests:
- `context.scenario` - Scenario-specific conditions
- `context.agent_version` - Agent version conditions
- `context.vm_name` - VM-specific conditions
- `context.installed_language_runtime` - Runtime version conditions
- Complex boolean logic combining non-library attributes
- `force_skip=True` requirement

If your condition depends only on library name, library version, or weblog variant, use the manifest file instead.

**After modifying any manifest file, always run `./format.sh`** to validate syntax and sort entries alphabetically.

## Decorator Types

* `@irrelevant`: The tested feature/behavior is irrelevant to the context. **Test is SKIPPED completely.**
* `@missing_feature`: The tested feature/behavior does not exist. **The test will be executed** and ignored if it fails. If it passes, a warning will be added in the output (`XPASS`).
* `@incomplete_test_app` (subclass of `missing_feature`): There is a deficit in the weblog/parametric apps that prevents validation.
* `@bug`: The lib does not implement the feature correctly. **The test will be executed** and ignored if it fails. If it passes, a warning will be added in the output (`XPASS`).
* `@flaky` (subclass of `bug`): The feature sometimes fails, sometimes passes. **Test is NOT executed by default.**

The decorators take several arguments:

* `condition`: boolean, tell if it's relevant or not. As it's the first argument, you can omit the arguement name
* `library`: provide library. version numbers are allowed e.g.`java@1.2.4`, see [versions.md](./versions.md) for more details on semantic versioning and testing against unmerged changes
* `weblog_variant`: if you want to skip the test for a specific weblog
* `reason`: why the test is skipped. It's especially useful for `@bug`, in which case the value should reference a JIRA ticket number.
* `force_skip`: if you want to not execute a test maked with `missing_feature` or `bug` (main reason it entirely break the app), you can set `force_skip` to `True`


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
