Three decorators allow you to skip test functions or classes for a library:

* `@irrelevant`: The tested feature/behavior is irrelevant to the library, meaning the feature is either purposefully not supported by the lib or cannot reasonably be implemented
* `@missing_feature`: The tested feature/behavior does not exist in the library or there is a deficit in the test library that blocks this test from executing for the lib. **The test will be executed** and being ignored if it fails. If it passes, a warning will be added in thee output (`XPASS`)
* `@incomplete_test_app` (sublass of `missing feature`): There is a deficit in the weblog/parametric apps or testing interface that prevents us from validating a feature across different applications.
* `@bug`: The lib does not implement the feature correctly/up to spec. **The test will be executed** and being ignored if it fails. If it passes, a warning will be added in thee output (`XPASS`)
* `@flaky` (subclass of `bug`): The feature sometimes fails, sometimes passes. It's not reliable, so don't run it.

To skip specific test functions within a test class, use them as in-line decorators (Example below).
To skip test classes or test files, use the decorator in the library's [manifest file](./manifest.md).

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
