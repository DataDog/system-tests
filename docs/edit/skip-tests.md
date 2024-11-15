Three decorators allow you to skip test functions or classes for a library:

* `@irrelevant`: The tested feature/behavior is irrelevant to the library, meaning the feature is either purposefully not supported by the lib or cannot reasonably be implemented
* `@bug`: The lib does not implement the feature correctly/up to spec
* `@flaky` (subclass of `bug`): The feature sometimes fails, sometimes passes. `flaky` skips the test.
* `@missing_feature`: The tested feature/behavior does not exist in the library or there is a deficit in the test library that blocks this test from executing for the lib

To skip specific test functions within a test class, use them as in-line decorators (Example below).
To skip test classes or test files, use the decorator in the library's [manifest file](./manifest.md).

The decorators take several arguments:

* `condition`: boolean, tell if it's relevant or not. As it's the first argument, you can omit the arguement name
* `library`: provide library. version numbers are allowed e.g.`java@1.2.4`, see [versions.md](./versions.md) for more details on semantic versioning and testing against unmerged changes
* `weblog_variant`: if you want to skip the test for a specific weblog
* `reason`: why the test is skipped. It's especially useful for `@bug`, in which case the value should reference a JIRA ticket number.


```python
from utils import irrelevant


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
```
