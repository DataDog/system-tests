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

It means that the test will be executed starting version `1.2.3`.

## Mark a class or a test case as bug

The `bug` decorator will skip a test or a test class. Please provide a small explanation of the bug, or better, a JIRA ref.

```python
from utils import BaseTestCase, bug

@bug(library="java", reason="APPSEC-666")
class Test_AwesomeFeature(BaseTestCase)
    """ Short description of Awesome feature """

    @bug(library="golang@0.2", reason="APPSEC-000")
    def test_basic(self)
        assert P==NP
```

## Mark a class or a test case as not relevant

```python
from utils import BaseTestCase, not_relevant


@not_relevant(library="nodejs")
class Test_AwesomeFeature(BaseTestCase)
    """ Short description of Awesome feature """

    def test_basic(self)
        assert P==NP

    @not_relevant(library="java@1.2.4", reason="still an hypothesis")
    def test_extended(self)
        assert riemann.zetas.zeros.real == 0.5
```

## Arguments

`@released` has several arguments, one per component name (`java`, `ruby`...). Simply provide a version number (the version where the feature has been implemented)

`@bug` and `@not_relevant` takes several conditional arguments:

* `condition`: boolean, tell if it's relevant or not. It's the first argument, si you can omit the arguement name
* `library`: provide library. version numbers are allowed (`java@1.2.4`)
* `weblog_variant`: if you want to skip the test for a specific weblog

And then, an `reason` argument with mor details. It's very handy for `@bug`, the best is providing a JIRA tickets number.
