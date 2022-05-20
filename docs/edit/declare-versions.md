Once you have written the test, as you have not yet implemented the feature, you must declare that the test is expected to fail until a given version number. You must use the `released` decorator for this, using the good component name and version number:

```python
from utils import BaseTestCase, released

@released(java="1.2.3")
class Test_AwesomeFeature(BaseTestCase)
    """ Short description of Awesome feature """
```

It means that the test will be executed starting version `1.2.3`. Arguments are components names, e.g. `java`, `golang`, etc... You can mix them on a single line.
Also, if a feature is not yet implemented, you can set the version as `?`. The test class will be be flagged as missing feature (see below). Note that it will be executed, and a warning will be reported if it succeed.

Sometimes, a version is working on a framework, and not one another one. You can provide a key-value object, where the key is your [weblog name]("./weblog.md) and the value is the version number. You can use `*` as a wildcard for the key.

```python
from utils import BaseTestCase, released

@released(python={"django": "1.2.3", "flask": "1.2.4", "*": "?"})
class Test_AwesomeFeature(BaseTestCase)
    """ Short description of Awesome feature """

    # supported on django starting 1.2.3
    # supported on flask starting 1.2.4
    # not yet supported on any other framework
```