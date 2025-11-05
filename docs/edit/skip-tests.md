Three decorators allow you to skip test functions or classes for a library:

* `@irrelevant`: The tested feature/behavior is irrelevant to the library, meaning the feature is either purposefully not supported by the lib or cannot reasonably be implemented
* `@missing_feature`: The tested feature/behavior does not exist in the library or there is a deficit in the test library that blocks this test from executing for the lib. **The test will be executed** and being ignored if it fails. If it passes, a warning will be added in thee output (`XPASS`)
* `@incomplete_test_app` (sublass of `missing feature`): There is a deficit in the weblog/parametric apps or testing interface that prevents us from validating a feature across different applications.
* `@bug`: The lib does not implement the feature correctly/up to spec. **The test will be executed** and being ignored if it fails. If it passes, a warning will be added in thee output (`XPASS`)
* `@flaky` (subclass of `bug`): The feature sometimes fails, sometimes passes. It's not reliable. By default, the test is skipped. However, you can enable automatic retries by specifying the `reruns` parameter, which will execute the test and retry it on failure.

To skip specific test functions within a test class, use them as in-line decorators (Example below).
To skip test classes or test files, use the decorator in the library's [manifest file](./manifest.md).

The decorators take several arguments:

* `condition`: boolean, tell if it's relevant or not. As it's the first argument, you can omit the arguement name
* `library`: provide library. version numbers are allowed e.g.`java@1.2.4`, see [versions.md](./versions.md) for more details on semantic versioning and testing against unmerged changes
* `weblog_variant`: if you want to skip the test for a specific weblog
* `reason`: why the test is skipped. It's especially useful for `@bug` and `@flaky`, in which case the value should reference a JIRA ticket number.
* `force_skip`: if you want to not execute a test maked with `missing_feature` or `bug` (main reason it entirely break the app), you can set `force_skip` to `True`
* `reruns`: (**`@flaky` only**) number of times to retry the test if it fails. If not specified, the test is skipped (default behavior). If specified, the test will run and retry up to N times on failure.
* `reruns_delay`: (**`@flaky` only**) delay in seconds between retry attempts. Only used when `reruns` is specified.

## @flaky Decorator Behavior

The `@flaky` decorator supports two modes of operation:

### Skip Mode (Default - Backward Compatible)
When `reruns` is **not** specified, the test is **skipped** entirely:
```python
@flaky(condition=True, reason="JIRA-1234")
def test_unreliable():
    pass  # Test will be SKIPPED
```

### Retry Mode (New)
When `reruns` is specified, the test will **execute** and automatically **retry** on failure:
```python
@flaky(condition=True, reason="JIRA-1234", reruns=3)
def test_unreliable():
    pass  # Test will RUN and retry up to 3 times if it fails
```

Optionally, you can add a delay between retry attempts:
```python
@flaky(condition=True, reason="JIRA-1234", reruns=3, reruns_delay=2)
def test_unreliable():
    pass  # Test will retry 3 times with 2 seconds between each attempt
```

**When to use retry vs skip:**
- **Use skip** (no `reruns`): When the test is completely broken or you want to temporarily disable it
- **Use retry** (with `reruns`): When the test has intermittent failures due to timing, race conditions, or eventually consistent systems

**Best practices:**
- Always include a JIRA ticket in the `reason` parameter
- Use reasonable retry counts (typically 2-5)
- Add delays (1-5 seconds) for timing-dependent tests
- Prefer fixing flaky tests over retrying them indefinitely

## Examples

```python
from utils import irrelevant, incomplete_test_app, bug, missing_feature, flaky


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

    # Flaky test - skipped by default (traditional behavior)
    @flaky(condition=True, reason="JIRA-1234")
    def test_flaky_skip(self):
        assert sometimes_fails()

    # Flaky test - with retry (new behavior)
    @flaky(condition=True, reason="JIRA-5678", reruns=3)
    def test_flaky_retry(self):
        assert sometimes_fails()  # Will retry up to 3 times

    # Flaky test - with retry and delay (new behavior)
    @flaky(condition=True, reason="JIRA-9999", reruns=3, reruns_delay=2)
    def test_flaky_retry_with_delay(self):
        assert eventually_consistent()  # Will retry 3 times with 2 second delay
```
