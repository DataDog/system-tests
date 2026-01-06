from utils import scenarios
from utils.docker_fixtures import TestAgentAPI
from .conftest import APMLibrary
from utils.docker_fixtures.spec.llm_observability import LlmObsSpanRequest  # TODO: unsure about this import


@scenarios.parametric
class TestEnablement:
    def test_ml_app(self, test_agent: TestAgentAPI, test_library: APMLibrary):  # noqa: ARG002
        llmobs_span_request = LlmObsSpanRequest(kind="task")  # noqa: F841
