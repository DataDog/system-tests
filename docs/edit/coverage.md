For each test class, you can add a coverage metadata. This information will be used on result usage, to help team to decide on wich part of the test they want to invest. The coverage gives a score to the test class, not to the feature. It also does not consider weblog variant implementation.

You can choose between 5 levels:

## No tests

The first two levels is suitable for test classes without any test method

## Implemented test coverage levels

The last three level are real coverage score for implemented tests

### Basic

``` python
@coverage.basic
```

This level is for minimal testing coverage. From a very basic smoke test to obvious test on main part of the feature, it guarantee that if the feature does not work at all, it will be catched. Though, no edge case nor [unhappy path](https://en.wikipedia.org/wiki/Happy_path) is tested.

### Good

``` python
@coverage.good
```

Almost all aspects of [happy paths](https://en.wikipedia.org/wiki/Happy_path) are tested, some edge case are considered. 

### Complete

``` python
@coverage.complete
```

Rock solid test. All path and edge case are tested, all visible effects are checked, all data type are validated. Any modification with a visible effect of the feature needs an adjustment on test class. A bug on this feature is highly unlikely if the test passes.
