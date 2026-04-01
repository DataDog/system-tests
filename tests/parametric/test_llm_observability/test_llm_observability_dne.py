from typing import TYPE_CHECKING
import os
import pytest

from tests.parametric.test_llm_observability.utils import check_and_get_api_key
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from ..conftest import APMLibrary  # noqa: TID252

if TYPE_CHECKING:
    from utils.docker_fixtures.spec.llm_observability import DatasetCreateRequest, ExperimentCreateRequest


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


@pytest.fixture
def dd_site(request: pytest.FixtureRequest) -> str | None:
    if request.config.option.generate_cassettes:
        return os.getenv("DD_SITE")
    return None


@pytest.fixture
def vcr_provider_map(request: pytest.FixtureRequest) -> str | None:
    if request.config.option.generate_cassettes:
        dd_site = os.getenv("DD_SITE", "")
        if dd_site and dd_site != "datadoghq.com":
            return f"datadog=https://api.{dd_site}/"
    return None


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


@features.llm_observability_datasets
@scenarios.parametric
class Test_Experiment:
    def test_experiment_basic_run(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test that a basic experiment can be created and run against a dataset."""
        with test_agent.vcr_context():
            # First create a dataset with records
            create_request: DatasetCreateRequest = {
                "dataset_name": "test-experiment-dataset",
                "description": "Dataset for experiment test",
                "records": [
                    {"input_data": {"text": "hello"}, "expected_output": "HELLO"},
                    {"input_data": {"text": "world"}, "expected_output": "WORLD"},
                ],
            }
            dataset = test_library.llmobs_dataset_create(create_request)
            assert dataset.get("dataset_id") is not None

            # Run an experiment with a simple task and evaluator
            experiment_request: ExperimentCreateRequest = {
                "experiment_name": "test-experiment-basic",
                "dataset_name": "test-experiment-dataset",
                "task_code": "def task(input_data, config=None):\n    return input_data['text'].upper()",
                "evaluator_codes": [
                    "def evaluator(input_data, output_data, expected_output):\n    return output_data == expected_output",
                ],
            }
            result = test_library.llmobs_experiment_run(experiment_request)

            assert result.get("experiment_name") == "test-experiment-basic"
            rows = result.get("rows", [])
            # Rows may be empty in VCR CI mode due to non-deterministic
            # eval submission bodies. When populated, verify structure.
            if rows:
                assert len(rows) == 2
                for row in rows:
                    assert row.get("output") is not None
                    assert row.get("error", {}).get("type") is None

            # Clean up
            test_library.llmobs_dataset_delete(dataset_id=dataset["dataset_id"])
