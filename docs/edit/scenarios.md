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
            there is some config error from the user.

            If any warmup must be executed at startup, they must be added here using self.warmups.add()
        """

    def post_setup(self, session):
        """ called after setup functions, and before test functions """

    def pytest_sessionfinish(self, session, exitstatus):
        """ Clean what need to be cleaned at the end of the test session """
```

Then define your scenario in a module of `utils/_context/_scenarios/`, grouped with similar scenarios if any. Its configuration lives in its class:

```python
from ._core import DdTraceEndToEndScenario


class CustomScenario(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__("CUSTOM_SCENARIO", weblog_env={"DD_SOME_SETTING": "true"}, doc="...")
```

And instantiate it in the `_Scenarios` class of `utils/_context/_scenarios/__init__.py`, without any argument:

```python
class _Scenarios:
    custom_scenario = CustomScenario()
```

`__init__.py` never contains any configuration: in CI, modifying it runs no scenario, while modifying a scenario module runs the scenarios it defines.

A scenario module only imports base classes from `._core`, which holds the ones shared by several modules (`EndToEndScenario`, `DdTraceEndToEndScenario`...). A base class used by a single module lives in this module, and is private (e.g. `_DebuggerScenario` in `debugger.py`).

Then, just flag you tests classes/methods with you scenario :

```python

@scenarios.custom_scenario
class Test_NewStuff:
    def test_main(self):
        assert 1+1 == 2
```
