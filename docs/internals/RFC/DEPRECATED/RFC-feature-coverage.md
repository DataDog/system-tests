## TL;DR.

We'll implement a mechanism that will put metadata on each test class about the coverage/completness of the test. Two questions :

- There will be three level, `basic`, `good`, `complete`. It's a compromise, do you think it's too many? not enough?
- Two proposition of implementations, one using decorators, and one using class inheritance :

```python
@coverage.good
class Test_Feature():
    pass
```

Or

```python
class Test_Feature(BaseTestCase.GoodCoverage):
    pass
```

There are pros and cons (see below), which one do you prefer ?

## Currently

For a given feature, a test can have two informal coverage status:

- The test is written. It provides a certain level of garantee for the feature to be bug-free
- The test is not written

The first status is obvious to observe (the test class exists), **but** there is no information about how far the test cover the feature. From bottom to top, it can be :

- just a declarative test (nothing is actually tested)
- indirect testing, it guess that the feature is working becase another one is working
- a simple smoke test
- a quite complete test
- a rock solid test, implying a very strong confidence on the feature

The second state is more ambigious. Often, the test class is missing, but we don't know if it's because the feature is not testable or if we can one day implement it.

This document will propose a mechanism to add metadata on test classes that allow to describe precisely the test coverage of each feature

## Possible test status

### Not testable

System test outputs are exported and used in metabase or google spreadsheets. As some feature are not testable, those UI needs to mix declartive data, and system test output. As an declarative test class is not harder than 2 code line, having this status will help us to have a complete automatic UI for feature status.

Furthermore, a feature is not testable, until we find a way to test them. With this status, we will save times and effort if it happens, as we won't have anything to change in system test output process.

### Not implemented

Obviously, it means that the test is not yet implemented

### Basic test

The test is the most simple test we can imagine for a feature. It ensure that the feature is working, but does not cover any subtility or edge cases

### Good test

The test fully covers the core functionnality of the feature. The test will catch all bug that can happen, except for edge cases and extreme scenarios

### Complete test

The test fully cover the functionnality, and missing a bug is statistically negligible => If a bug is missed, we should be included in the post mortem and review our understanding of the feature

______________________________________________________________________

There is three level for an implemented test. It's a compromise between too many levels with blurry boundaries, and not enough to describe what we want. Feel free to challenge them.

## Implementation

```python
@coverage.not_testable  # DEPRECATED: this information exists in the feature parity dashbaord
class Test_Feature():
    pass

@coverage.not_implemented  # DEPRECATED: this information exists in the feature parity dashbaord
class Test_Feature():
    pass

@coverage.basic
class Test_Feature():
    pass

@coverage.good
class Test_Feature():
    pass

@coverage.complete
class Test_Feature():
    pass
```

The test coverage will be used to have actionnables on test implementations. In consequence, it must be unique for a given test class. If more than one is used, an exception is raised

```python
@coverage.basic
@coverage.good
class Test_Feature():
    pass

# => error
```

In particular, weblog missing endpoints can't have impact on test coverage, as there is nothing to do on the test class. We must use `missing_feature` for this use case (yes, it is a missing feature, *test is a true part of the feature*) :

```python
@coverage.basic
@missing_feature(library="golang", context.weblog_variant="gin", reason="Missing weblog endpoint")
class Test_Feature():
    pass

# => the coverage is "basic", and the test will be flagged as missing feature for golang/gin
```

The `@coverage` decorator can't be used on methods

### Other implemention : Using base test class inheritance

This implementation has not been chosen because :

- it would make the delcaration mandatory => causes friction
- it uses another mechanism to declare metadata => causes friction

Pro would be:

- save one code line => code lines are free
- simpler to implement => less effort on our side, more effort on user side. And decorator are simple enough.

```python
class Test_Feature(BaseTestCase.NotTestable):
    pass

class Test_Feature(BaseTestCase.NotImplemented):
    pass

class Test_Feature(BaseTestCase.BasicCoverage):
    pass

class Test_Feature(BaseTestCase.GoodCoverage):
    pass

class Test_Feature(BaseTestCase.CompleteCoverage):
    pass
```

## Impact on feature status

### not_testable

DEPRECATED: this information exists in the feature parity dashbaord

- if one or more test method exists, and exception will be raised at test collection
- feature is marked as `passed`

### not_implemented

DEPRECATED: this information exists in the feature parity dashbaord

- if one or more test method exists, and exception will be raised at test collection
- Feature is marked as `missing feature`

### Others

- No effect on skipping mechanism, the feature is marked regarding the test output
