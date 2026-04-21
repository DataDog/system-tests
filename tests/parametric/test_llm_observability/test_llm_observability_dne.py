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
        """Test that an experiment can run a task over a dataset and return results.

        Mirrors dd-trace-py test_experiment_run: verifies that experiment.run()
        returns rows with correct input, output, expected_output, and evaluations.
        """
        with test_agent.vcr_context():
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

            experiment_request: ExperimentCreateRequest = {
                "experiment_name": "test-experiment-basic",
                "dataset_name": "test-experiment-dataset",
                "task": "uppercase",
                "evaluators": ["exact_match"],
            }
            result = test_library.llmobs_experiment_run(experiment_request)

            assert result.get("experiment_name") == "test-experiment-basic"

            rows = result.get("rows", [])
            assert len(rows) == 2

            for row in rows:
                # Task produced output
                assert row.get("output") is not None
                # No task errors
                assert row.get("error", {}).get("type") is None
                # Input and expected_output are present (mirrors dd-trace-py assertions)
                assert row.get("input") is not None
                assert row.get("expected_output") is not None

            # Verify specific row content
            outputs = sorted(row["output"] for row in rows)
            assert outputs == ["HELLO", "WORLD"]

            # Verify evaluations ran (exact_match evaluator)
            for row in rows:
                evals = row.get("evaluations", {})
                assert "_evaluator_exact_match" in evals
                assert evals["_evaluator_exact_match"]["value"] is True

            # Clean up
            test_library.llmobs_dataset_delete(dataset_id=dataset["dataset_id"])
