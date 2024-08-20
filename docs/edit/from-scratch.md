Current system-tests implements mostly functional end-to-end scenario. But it an achieve any test paradigm you like. Build uppon pytest, it introduces a simple - an extensible - object: `Scenario`.

A scenario is the abstraction for a context to test, and anything can be defined inside this context. Here is the most simple context scenario you can imagine :


### `utils/_context/_scenarios/custom_scenario.py`

```python
from .core import Scenario

class CustomScenario(Scenario):
    def session_start(self, session):
        """ if needed, use this function to start anything needed to your scenario """

    def pytest_sessionfinish(self):
        """ if needed, clean what need to be cleaned at the end of the test session"
```

And include you scenario in `utils/_context/_scenarios/__init__.py`

Then, just flag you tests classes/methods with you scenario :

```python

@scenarios.custom_scenario
class Test_NewStuff:
    def test_main(self):
        assert 1+1 == 2
```
