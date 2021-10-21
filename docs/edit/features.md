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

## Skip special use case

Sometimes, a test must be skipped for different reason. For this, use the `skipif` decorator :


```python
from utils import BaseTestCase, released, skipif, context

@released(java="1.2.3")
class Test_AwesomeFeature(BaseTestCase)
    """ Short description of Awesome feature """

    def test_basic(self)
        assert P==NP

    @skipif(context.library=="java@1.2.4", reason="not relevant: still an hypothesis")
    def test_extended(self)
        assert riemann.zetas.zeros.real == 0.5
```

`skipif` takes two arguments:

1. A boolean, obviously the skip condition. The `context` object will provide all sort of information about the test context for this. Here are some example : 
    * `context.library == "ruby"`
    * `context.library in ("python", "nodejs"`
    * `context.library == "java@4.28"`
    * `context.library < "dotnet@1.28.5"`
2. A skip reason. It **must** start with one this:   
    * `not relevant`: When this test is not relevant (again, a small explanation is welcome)
    * `missing feature`: When this spcial use case is not yet implemented.
