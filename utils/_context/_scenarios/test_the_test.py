from utils._context.component_version import ComponentVersion
from .core import Scenario


class TestTheTestScenario(Scenario):
    library = ComponentVersion("java", "0.66.0")
    agent_version = ComponentVersion("agent", "0.77.0").version

    def __init__(self, name: str, doc: str) -> None:
        super().__init__(name, doc=doc, github_workflow="testthetest")
        self.components["mock_comp1"] = "mock_comp1_value"

    @property
    def parametrized_tests_metadata(self):
        return {"tests/test_the_test/test_json_report.py::Test_Mock::test_mock": {"meta1": "meta1"}}

    @property
    def weblog_variant(self):
        return "spring"
