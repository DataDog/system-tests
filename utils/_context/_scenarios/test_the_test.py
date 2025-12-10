import pytest
from utils._context.component_version import ComponentVersion, NoneVersion
from .core import Scenario


class TestTheTestScenario(Scenario):
    library = ComponentVersion("java", "0.66.0")
    agent_version = ComponentVersion("agent", "0.77.0").version

    def __init__(self, name: str, doc: str) -> None:
        super().__init__(name, doc=doc, github_workflow="testthetest")
        self.components["mock_comp1"] = NoneVersion()

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
