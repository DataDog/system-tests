Current system-tests implements mostly functional end-to-end scenario. But it can achieve any test paradigm you like. Build uppon pytest, it introduces a simple - and extensible - object: `Scenario`.

A scenario is the abstraction for a context to test, and anything can be defined inside this context. Here is the most simple context scenario you can imagine :


### `utils/_context/_scenarios/custom_scenario.py`

```python
from .core import Scenario

class CustomScenario(Scenario):
    def configure(self, config:pytest.Config):
        """
            If needed, configure the context => mainly, only get infos from config
            At this point, logger.stdout is unavailable, so this function should not fail, unless
            there is some config error from the user
        """

    def get_warmups(self):
        """
            Use this function to start anything needed to your scenario (build, run targets)
            This function returns a list of callable that will be called sequentially
        """
        warmups = super().get_warmups()

        warmups.append(self.start_target)

        return warmups

    def post_setup(self, session):
        """ called after setup functions, and before test functions """

    def pytest_sessionfinish(self, session, exitstatus):
        """ Clean what need to be cleaned at the end of the test session """
```

And include you scenario in `utils/_context/_scenarios/__init__.py`

Then, just flag you tests classes/methods with you scenario :

```python

@scenarios.custom_scenario
class Test_NewStuff:
    def test_main(self):
        assert 1+1 == 2
```
