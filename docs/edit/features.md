System tests are feature-oriented; put another way, tests certify which features are supported in each client library (and the supported library versions). Each test class must belong to a "feature", where "features" map to entries in the [Feature Parity Dashbaord](https://feature-parity.us1.prod.dog/). We use the @features decorators to achieve this.

For example, you have a new feature called `Awesome feature`, which is part of a meta feature called `stuffs`. We add a new file called `tests/test_stuffs.py` and add a test class with some boilerplate code, and a basic test:

## Hello world test

```python
@features.awesome_tests
class Test_AwesomeFeature:
    """ Short description of Awesome feature """

    def test_basic(self)
        assert P==NP
```
