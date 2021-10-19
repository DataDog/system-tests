The workflow is very simple: add your test case, commit into a branch and create a PR. We'll review it ASAP.

Depending of how far is your test from an existing tests, it'll ask you some effort. The very first step is to add it and execute it. For instance, in a new file `tests/test_some_feature.py`:

```python
class Test_Feature():
    def test_feature_detail(self):
        assert 1 + 1 == 2
```

Please note that you don't have to rebuild images at each iteration. Simply re-run `run.sh`. And you can also specify the test you want to run, don't be overflooded by logs: 

```
./run.sh tests/test_some_feature.py::Test_Feature::test_feature_detail
```

You now want to send something on the [weblog](../edit/weblog.md), and check it. You need to inherits from `BaseTestCase`, and use an interface validator:

```python
from utils import BaseTestCase, interfaces


class Test_Feature(BaseTestCase):
    def test_feature_detail(self):
        """ tests an awesome feature """
        r = self.weblog_get("/url")
        interfaces.library.add_span_validation(r, lamda span: span["meta"]["http.method"] == "GET")
```

And it's also a good idea to [provide meta info about your feature, and sometimes skip a test](./features.md).

```python
from utils import BaseTestCase, interfaces, context, skipif, released


@released(ruby="1.2.3")
class Test_Feature(BaseTestCase):

    @skipif(context.library == "ruby", reason="Known bug: APPSEC-123")
    def test_feature_detail(self):
        """ tests an awesome feature """
        r = self.weblog_get("/url")
        interfaces.library.add_span_validation(r, lamda span: span["meta"]["http.method"] == "GET")
```

You now have the basics. It proably won't be as easy, and you may needs to dive into internals, so please do not hesitate to ask for help on slack at [#apm-integrations-reliability-and-performance-team](https://dd.slack.com/archives/C01CGB22DC2)