When you add a test class (see [features](./features.md)), you need to declare what feature it belongs to in the [Feature Parity Dashbaord](https://feature-parity.us1.prod.dog/). To achieve that, use `@features` decorators :

```python
@features.awesome_tests
class Test_AwesomeFeature:
    """ Short description of Awesome feature """
```

## Use case 1: The feature already exists

The link to the feature is in the docstring: hover the name, this link will show up.

## Use case 2: the feature does not exists

1. Create it in [Feature Parity Dashbaord](https://feature-parity.us1.prod.dog/)
1. pick its feature ID (the number in the URL)
1. copy pasta in `utils/_features.py` (its straightforward)

______________________________________________________________________

If you need any help, please ask on [slack](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X)
