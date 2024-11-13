Whether it's adding a new test or modifying an existing test, a moderate amount of effort will be required. The instructions below cater to weblog tests, but refer to [placeholder] (link to contributing doc) for contributing to parametric tests.

Once the changes are complete, post them in a PR. We'll review it ASAP.

#### Notes
* Each test class tests only one feature
* A test class can have several tests
* If an RFC for the feature exists, you must use the decorator `rfc` decorator:
```python
from utils import rfc


@rfc("http://www.claymath.org/millennium-problems")
class Test_Millenium:
    """ Test on small details """
```

In most cases, you'll only need to add a new test class or function. But if you need to add a new scenario, refer to [scenarios.md](./scenarios.md).

---

Tests live under the `tests/` folder. You may need to add a new file to this folder, or a new directory + file to this folder. Alternatively, you may add a test to an existing file, if it makes sense. Tests are structured like so, e.g. `tests/test_some_feature.py`:

```python
class Test_Feature():
    def optional_test_setup(self):
        my_var = 1
    def test_feature_detail(self):
        assert my_var + 1 == 2
```

No need to rebuild images at each iteration. Simply re-run `run.sh` to re-run (and build) your test:

```
./run.sh tests/test_some_feature.py::Test_Feature::test_feature_detail
```

Weblog apps will perform the instrumentation you want to test, so you'll probably want to send a request to the [weblog](../edit/weblog.md) and inspect it. The weblogs already have existing endpoints that perform some behaviors; perhaps you can use an existing endpoint, or you may need to add a new one. The weblog will then send back information about the behavior; this is the information your test will need to inspect, and you can use an interface validator to do so:

```python
from utils import weblog, interfaces


class Test_Feature():
    def setup_feature_detail(self):
        self.r = weblog.get("/url")

    def test_feature_detail(self):
        """ tests an awesome feature """
        interfaces.library.validate_spans(self.r, lamda span: span["meta"]["http.method"] == "GET")
```

Sometimes [skip a test](./features.md) is needed.

```python
from utils import weblog, interfaces, context, bug


class Test_Feature():

    def setup_feature_detail(self):
        self.r = weblog.get("/url")

    @bug(library="ruby", reason="APPSEC-123")
    def test_feature_detail(self):
        """ tests an awesome feature """
        interfaces.library.validate_spans(self.r, lamda span: span["meta"]["http.method"] == "GET")
```

You now have the basics. Expect to dive into the test internals, but feel free to ask for help on slack at [#apm-shared-testing](https://dd.slack.com/archives/C025TJ4RZ8X)
