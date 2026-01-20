"""
Tests for LLM Observability Datasets and Experiments (DNE) feature.

These tests validate that tracer libraries correctly implement the DNE API
for creating, managing, and deleting datasets.

These tests use VCR cassettes to mock backend API responses.
"""

import pytest

from utils import scenarios, features
from utils.docker_fixtures import TestAgentAPI
from ..conftest import APMLibrary
from utils.docker_fixtures.spec.llm_observability import (
    DatasetCreateRequest,
    DatasetDeleteRequest,
)


@pytest.fixture
def library_env(
    llmobs_ml_app: str, llmobs_project_name: str, test_agent: TestAgentAPI, *, llmobs_enabled: bool
) -> dict[str, object]:
    """Environment variables for LLM Observability DNE tests."""
    # Point LLMObs API calls to test agent's VCR proxy for cassette playback
    override_origin = f"http://{test_agent.container_name}:{test_agent.container_port}/vcr/datadog"

    env = {
        "DD_LLMOBS_ENABLED": llmobs_enabled,
        "DD_LLMOBS_ML_APP": llmobs_ml_app,
        "DD_LLMOBS_PROJECT_NAME": llmobs_project_name,
        # Route LLMObs API calls through the test agent's VCR proxy
        "DD_LLMOBS_OVERRIDE_ORIGIN": override_origin,
        # Fake API key for VCR mode (actual auth is bypassed)
        "DD_API_KEY": "fake-api-key-for-vcr-testing",
    }
    return env


# TODO: Add feature decorator once DNE feature is registered in feature parity
# @features.llm_observability_datasets_and_experiments
@scenarios.parametric
class Test_Dataset_Create:
    """Tests for basic dataset creation."""

    def test_dataset_create_delete(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test that a dataset can be created and deleted.

        This is the most basic DNE test - verifying that:
        1. A dataset can be created with just a name and description
        2. The dataset is assigned an ID
        3. The dataset can be deleted by ID
        """
        with test_agent.vcr_context():
            # Create a dataset
            create_request = DatasetCreateRequest(
                dataset_name="test-dataset-basic",
                description="A basic test dataset",
            )
            dataset = test_library.llmobs_dataset_create(create_request)

            # Verify dataset was created
            assert dataset is not None
            assert dataset.dataset_id is not None
            assert dataset.name == "test-dataset-basic"
            assert dataset.description == "A basic test dataset"
            assert dataset.project_name == "test-project"

            # Clean up - delete the dataset
            delete_request = DatasetDeleteRequest(dataset_id=dataset.dataset_id)
            result = test_library.llmobs_dataset_delete(delete_request)
            assert result.get("success") is True
