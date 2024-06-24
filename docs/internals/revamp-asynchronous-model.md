## TL;DR.

- We will revamp tests execution logic.
- **goal**: Reduce the overall complexity of system test internals
- **drawback**: Weblog requests will no longer be in the same test function
- **added values**: It'll be easier to run and debug test logics. And using native pytest feature, we'll be able to include parametric test in system tests.

### Test code before

```python
class Test_Feature(BaseTestCase):
    """A test on a feature"""

    def test_main(self):

        def validator(trace):
            assert "feature" in trace

        r = self.weblog_get("/feature")
        interfaces.library.add_trace_assertion(r, validator)
```

### Test code after

```python
class Test_Feature(BaseTestCase):
    """A test on a feature"""

    def setup_main(self):
        self.r = self.weblog_get("/feature")

    def test_main(self):
        for trace in interfaces.library.get_traces_related_to(request=self.r)
            assert "feature" in trace
```

## Revamp description

As now, all validation are made asynchronously, after the end of the test session. It comes with a lot of hack around pytest, and, as a consequence, make harder to debug test logic, and requires a minimum understanding of the asynchronous logic.

Furthermore, as the test function does not have any test logic, they must not fail, which is a non-sense from pytest perspective. For instance, any error when writing a test on a `xfail` method is interpreted as normal by pytest, making writing conplex test hard.

Cherry on the (bad) cake, we have lot of unecessary complexity to gater logs, and overwrite test results and the end of the test session.

Considering that it could have been written, slighlty differently, putting everything at the right place in the pytest world, we can call the actual design a bad design. To sum up the change we consider, here is every step, with the before/after location:

Step                       | Before                                                                     | After
-------------------------- | -------------------------------------------------------------------------- | ----------------------------------
Weblog warmup              | custom test executor                                                       | pytest_collection_finished
Setup test cases           | custom test executor, calling test functions (that must not fail)          | pytest_collection_finished, the only hacky part of the new model
Wait for everything happen | custom test executor                                                       | pytest_collection_finished
Test logic                 | custom test executor calls all asynchronous validation                     | Not needed, working out-of-the box
collect logs               | pytest_terminal_summary, with lot of hack to collect logs and metadata     | Not needed, working out-of-the box
Overwrite test result      | pytest_json_modifyreport, with lot of hacks                                | Not needed, working out-of-the box

**In few words, we put the `setup` and `wait` step after the test collection, and nothing else is needed. Rather than rewritting a test executor, and lot of hacks**.

## Drawback

One nice feature of the actual system if that if a feature needs an weblog HTTP request to be tested, this request is in the test method. And even if test logic is not **in** the test function (mostly in a nested function, or directly in some system test internal, like `assert_waf_attack(request)`), it's close enough to be easily understable. With the new model, it must be in a separated method. We'll try to mitigate this slighlty bigger distance by organizing test classes to keep every setup method just above the associated test method.
