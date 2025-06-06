Whether it's adding a new test or modifying an existing test, a moderate amount of effort will be required. The instructions below cater to end-to-end tests, refer to [the parametric contributing doc](/docs/scenarios/parametric_contributing.md)for parametric-specific instructions.

Once the changes are complete, post them in a PR.

#### Notes
* Each test class tests only one feature (see [the doc on features](https://github.com/DataDog/system-tests/blob/main/docs/edit/features.md))
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

The weblog apps are responsible for generating instrumentation. Your test should send a request to the weblog and inspect the response. There are various endpoints on weblogs for performing dedicated behaviors (e.g, starting a span, etc). When writing a new test, you might use one of the existing endpoints or create a new one if needed. To validate the response from the weblog, you can use an interface validator:

```python
from utils import weblog, interfaces


class Test_Feature():
    def setup_feature_detail(self):
        self.r = weblog.get("/url")

    def test_feature_detail(self):
        """ tests an awesome feature """
        interfaces.library.validate_spans(self.r, validator=lamda span: span["meta"]["http.method"] == "GET")
```

Sometimes you need to [skip a test](./skip-tests.md):

```python
from utils import weblog, interfaces, context, bug


class Test_Feature():

    def setup_feature_detail(self):
        self.r = weblog.get("/url")

    @bug(library="ruby", reason="APPSEC-123")
    def test_feature_detail(self):
        """ tests an awesome feature """
        interfaces.library.validate_spans(self.r, validator=lamda span: span["meta"]["http.method"] == "GET")
```

You'll need to build the images at least once, so if you haven't yet, run the `build` command. After the first build, you can just re-run the tests using the `run` command.

- build: `build.sh <library_name> [options...]`, see [build documentation](../execute/build.md) for more info
- run: `./run.sh tests/test_some_feature.py::Test_Feature::test_feature_detail`, see [run documentation](../execute/run.md) for more info

You now have the basics. Expect to dive into the test internals, but feel free to ask for help on slack at [#apm-shared-testing](https://dd.slack.com/archives/C025TJ4RZ8X)
