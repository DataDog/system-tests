A `DockerFixturesScenario` is a scenario category where each test will use a dedicated Test Agent and Test Librariry container.

The name comes from pytest fixture, which is the mechanism that allow a test method to get information about test context :


```python
@scenarios.parametric
def test_stuff(test_library):
    assert test_library.is_running()  # test_library is an API against a tested container
```