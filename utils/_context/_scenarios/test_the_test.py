import pytest
from utils._context.component_version import ComponentVersion, Version
from ._core import DockerScenario, Scenario, scenario_groups


class _TestTheTestScenario(Scenario):
    library = ComponentVersion("java", "0.66.0")
    agent_version = ComponentVersion("agent", "0.77.0").version

    def __init__(
        self,
        name: str,
    ) -> None:
        super().__init__(name, github_workflow="testthetest")
        self.components["mock_comp1"] = Version("0.0.1")

    @property
    def parametrized_tests_metadata(self):
        return {"tests/test_the_test/test_json_report.py::Test_Mock::test_mock": {"meta1": "meta1"}}

    @property
    def weblog_variant(self):
        return "spring"

    def configure(self, config: pytest.Config) -> None:
        super().configure(config)

        self.warmups.append(self._set_components)

    def _set_components(self) -> None:
        self.components["library"] = self.library.version
        self.components[self.library.name] = self.library.version
        self.components["agent"] = self.agent_version


class Todo(Scenario):
    """scenario that skips tests not yet executed"""

    def __init__(self) -> None:
        super().__init__("TODO", github_workflow=None)


class TestTheTest(_TestTheTestScenario):
    """Small scenario that check system-tests internals"""

    def __init__(self) -> None:
        super().__init__("TEST_THE_TEST")


class MockTheTest(_TestTheTestScenario):
    """Mock scenario that check system-tests internals"""

    def __init__(self) -> None:
        super().__init__("MOCK_THE_TEST")


class MockTheTest2(_TestTheTestScenario):
    """Mock scenario that check system-tests internals"""

    def __init__(self) -> None:
        super().__init__("MOCK_THE_TEST_2")


class Fuzzer(DockerScenario):
    """Fake scenario for fuzzing (launch without pytest)"""

    def __init__(self) -> None:
        super().__init__(
            "FUZZER",
            github_workflow=None,
            scenario_groups=[scenario_groups.exotics],
        )
