System tests are feature-oriented; put another way, tests certify which features are supported in each client library (and the supported library versions). Each test class must belong to a "feature", where "features" map to entries in the [Feature Parity Dashboard](https://feature-parity.us1.prod.dog/). We use the `@features` decorators to achieve this.

For example, you have a new feature called `Awesome feature`, which is part of a meta feature called `stuffs`. We add a new file called `tests/test_stuffs.py` and add a test class with some boilerplate code, and a basic test:

## Hello world test

```python
@features.awesome_tests
class Test_AwesomeFeature:
    """ Short description of Awesome feature """

    def test_basic(self)
        assert P==NP
```

Several key points:

* Each new feature should be defined in [_features.py](/utils/_features.py). This consists of adding a feature in [Feature Parity Dashboard](https://feature-parity.us1.prod.dog/), get the feature id and copying one of the already added features, changing the name and the feature id in the url, and the feature number. In this case we'd add

```python

    @staticmethod
    def awesome_feature(test_object):
        """
        Awesome Feature for Awesomeness

        https://feature-parity.us1.prod.dog/#/?feature=291
        """
        pytest.mark.features(feature_id=291)(test_object)
        return test_object
```

* One class tests one feature
* One class can have several tests
* Files can be nested (`tests/test_product/test_stuffs.py::Test_AwesomeFeature`), and how files are organized does not make any difference. Use you common sense, or ask on [slack](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X).

## Skip tests

See [skip-tests.md](/docs/edit/skip-tests.md)