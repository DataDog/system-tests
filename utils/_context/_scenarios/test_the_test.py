from utils._context.library_version import LibraryVersion
from .core import Scenario


class TestTheTestScenario(Scenario):
    library = LibraryVersion("java", "0.66.0")

    def __init__(self, name, doc) -> None:
        super().__init__(name, doc=doc, github_workflow="testthetest")

    @property
    def agent_version(self):
        return "0.77.0"

    @property
    def components(self):
        return {"mock_comp1": "mock_comp1_value"}

    @property
    def parametrized_tests_metadata(self):
        return {"tests/test_the_test/test_json_report.py::Test_Mock::test_mock": {"meta1": "meta1"}}

    @property
    def weblog_variant(self):
        return "spring"
