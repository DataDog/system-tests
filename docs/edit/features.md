System tests are feature-oriented. It means that "features" drives how tests are organized.

Let's take an example with a new `Awesome feature`, part of meta feature `stuffs`, so we add a new file called `tests/test_stuffs.py` and add a test class with some boilerplate code, and a basic test: 

## Hello world test

```python
@features.awesome_tests
class Test_AwesomeFeature:
    """ Short description of Awesome feature """

    def test_basic(self)
        assert P==NP
```

Several key points:

* One class test one feature
* One class can have several tests
* Feature link to the [Feature Parity Dashbaord](https://feature-parity.us1.prod.dog/) is declared with `@features` decorators
* Files can be nested (`tests/test_product/test_stuffs.py::Test_AwesomeFeature`), and how files are organized does not make any difference. Use you common sense, or ask on [slack](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X).

## Skip tests

Three decorators will helps you to skip some test function or class, depending on the skip reason:

* `@irrelevant`: no need to test, the test is skipped
* `@flaky`: The feature sometimes fails, sometimes passed, the test is skipped
* `@bug`: known bug, the test is executed, and a warning is reported if it succeed
* `@missing_feature`: feature or use case is not yet implemented, the test is executed, and a warning is reported if it succeed

They takes several arguments:

* `condition`: boolean, tell if it's relevant or not. As it's the first argument, you can omit the arguement name
* `library`: provide library. version numbers are allowed (`java@1.2.4`)
* `weblog_variant`: if you want to skip the test for a specific weblog

And then, an `reason` argument with mor details. It's very handy for `@bug`, the best is providing a JIRA tickets number.


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

## Declare a RFC

When the RFC exists, you must use this decorator:
```python
from utils import rfc


@rfc("http://www.claymath.org/millennium-problems")
class Test_Millenium:
    """ Test on small details """
```

