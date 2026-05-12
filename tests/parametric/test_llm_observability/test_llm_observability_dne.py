from typing import TYPE_CHECKING
import pytest

from tests.parametric.test_llm_observability.utils import check_and_get_api_key
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from ..conftest import APMLibrary  # noqa: TID252

if TYPE_CHECKING:
    from utils.docker_fixtures.spec.llm_observability import DatasetCreateRequest


@pytest.fixture
def llmobs_override_origin(test_agent: TestAgentAPI) -> str:
    return f"http://{test_agent.container_name}:{test_agent.container_port}/vcr/datadog"


@pytest.fixture
def llmobs_project_name() -> str:
    return "test-project"


@pytest.fixture
def dd_api_key(request: pytest.FixtureRequest) -> str | None:
    return check_and_get_api_key("DD_API_KEY", generate_cassettes=request.config.option.generate_cassettes)


@pytest.fixture
def dd_app_key(request: pytest.FixtureRequest) -> str | None:
    return check_and_get_api_key("DD_APP_KEY", generate_cassettes=request.config.option.generate_cassettes)


@features.llm_observability_datasets
@scenarios.parametric
class Test_Dataset:
    def test_dataset_create_delete(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test that a dataset can be created and deleted."""
        with test_agent.vcr_context():
            create_request: DatasetCreateRequest = {
                "dataset_name": "test-dataset-basic",
                "description": "A basic test dataset",
            }
            dataset = test_library.llmobs_dataset_create(create_request)

            assert dataset.get("dataset_id") is not None
            assert dataset.get("name") == "test-dataset-basic"
            assert dataset.get("description") == "A basic test dataset"
            assert dataset.get("project_name") == "test-project"

            result = test_library.llmobs_dataset_delete(dataset_id=dataset["dataset_id"])
            assert result.get("success") is True
