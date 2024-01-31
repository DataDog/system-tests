## Run the test loccally

Please have a look on the [weblog](../execute/)

```bash
./build.sh python  # or any another library. This step can be ran only once, as long as you do not need a modification on the lib/agent
./run.sh
```

That's it. If you're using VScode with Python extension, your terminal will automatically switch to the virtual env, and you will be able to use lint/format tools.

## Propose a modification

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

You now want to send something on the [weblog](../edit/weblog.md), and check it. You need to use an interface validator:

```python
from utils import weblog, interfaces


class Test_Feature():
    def setup_feature_detail(self):
        self.r = weblog.get("/url")

    def test_feature_detail(self):
        """ tests an awesome feature """
        interfaces.library.validate_spans(self.r, lamda span: span["meta"]["http.method"] == "GET")
```

Sometimes [skip a test](./features.md) is needed

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

You now have the basics. It proably won't be as easy, and you may needs to dive into internals, so please do not hesitate to ask for help on slack at [#apm-shared-testing](https://dd.slack.com/archives/C025TJ4RZ8X)
