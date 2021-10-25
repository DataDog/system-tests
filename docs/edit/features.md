System tests are feature-oriented. It means that "features" drives how tests are organized.

Let's take an example with a new `Awesome feature`, part of meta feature `stuffs`, so we add a new file called `tests/test_stuffs.py` and add a test class with some boilerplate code, and a basic test: 

## Hello world test

```python
from utils import BaseTestCase

class Test_AwesomeFeature(BaseTestCase)
    """ Short description of Awesome feature """

    def test_basic(self)
        assert P==NP
```

Several key points:

* One class test one feature
* One class can have several tests
* Files can be nested (`tests/test_product/test_stuffs.py::Test_AwesomeFeature`), feature's identifier will be the entire path, include the class name

## Declare versions

Once you have written the test, as you have not yet implemented the feature, you must declare that the test is expected to fail until a given version number. You must use the `released` decorator for this, using the good component name and version number:

```python
from utils import BaseTestCase, released

@released(java="1.2.3")
class Test_AwesomeFeature(BaseTestCase)
    """ Short description of Awesome feature """
```

It means that the test will be executed starting version `1.2.3`. Arguments are components names, e.g. `java`, `golang`, etc... You can mix them on a single line. 

## Skip tests

Three decorators will helps you to skip some test function or class, depending on the skip reason:

* `@not_relevant`: no need to test
* `@missing_feature`: feature or use case is not yet implemented
* `@bug`: known bug

They takes several arguments:

* `condition`: boolean, tell if it's relevant or not. As it's the first argument, you can omit the arguement name
* `library`: provide library. version numbers are allowed (`java@1.2.4`)
* `weblog_variant`: if you want to skip the test for a specific weblog

And then, an `reason` argument with mor details. It's very handy for `@bug`, the best is providing a JIRA tickets number.


```python
from utils import BaseTestCase, not_relevant


@not_relevant(library="nodejs")
class Test_AwesomeFeature(BaseTestCase)
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
