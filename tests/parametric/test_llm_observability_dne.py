"""
Tests for LLM Observability Datasets and Experiments (DNE) feature.

These tests validate that tracer libraries correctly implement the DNE API
for creating, managing, and deleting datasets.

These tests use VCR cassettes to mock backend API responses.
"""

import pytest

from utils import scenarios, features
from utils.docker_fixtures import TestAgentAPI
from .conftest import APMLibrary
from utils.docker_fixtures.spec.llm_observability import (
    DatasetCreateRequest,
    DatasetDeleteRequest,
    DatasetRecordRequest,
)


@pytest.fixture
def llmobs_enabled() -> bool:
    return True


@pytest.fixture
def llmobs_ml_app() -> str:
    return "test-ml-app"


@pytest.fixture
def llmobs_project_name() -> str:
    return "test-project"


@pytest.fixture
def library_env(
    llmobs_ml_app: str, llmobs_project_name: str, test_agent: TestAgentAPI, *, llmobs_enabled: bool
) -> dict[str, object]:
    """Environment variables for LLM Observability DNE tests."""
    # Point DNE client to test agent's VCR proxy for cassette playback
    dne_intake_url = f"http://{test_agent.container_name}:{test_agent.container_port}/vcr/datadog"

    env = {
        "DD_LLMOBS_ENABLED": llmobs_enabled,
        "DD_LLMOBS_ML_APP": llmobs_ml_app,
        "DD_LLMOBS_PROJECT_NAME": llmobs_project_name,
        # Route DNE API calls through the test agent's VCR proxy
        "DD_LLMOBS_DNE_INTAKE_URL": dne_intake_url,
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

    def test_dataset_create_with_records(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test that a dataset can be created with initial records.

        Verifies that:
        1. Records can be provided during dataset creation
        2. Records have input_data and expected_output
        3. The dataset contains the expected number of records
        """
        with test_agent.vcr_context():
            records = [
                DatasetRecordRequest(
                    input_data={"prompt": "What is the capital of France?"},
                    expected_output={"answer": "Paris"},
                ),
                DatasetRecordRequest(
                    input_data={"prompt": "What is the capital of Germany?"},
                    expected_output={"answer": "Berlin"},
                ),
            ]

            create_request = DatasetCreateRequest(
                dataset_name="test-dataset-with-records",
                description="A test dataset with records",
                records=records,
            )
            dataset = test_library.llmobs_dataset_create(create_request)

            # Verify dataset was created with records
            assert dataset is not None
            assert dataset.dataset_id is not None
            assert dataset.name == "test-dataset-with-records"
            assert len(dataset.records) == 2

            # Verify record contents
            # Note: records may not be returned in the same order
            record_inputs = [r["input_data"] for r in dataset.records]
            assert {"prompt": "What is the capital of France?"} in record_inputs
            assert {"prompt": "What is the capital of Germany?"} in record_inputs

            # Clean up
            delete_request = DatasetDeleteRequest(dataset_id=dataset.dataset_id)
            test_library.llmobs_dataset_delete(delete_request)

    def test_dataset_create_with_metadata(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test that a dataset can be created with records containing metadata.

        Verifies that:
        1. Records can include metadata
        2. Metadata is preserved in the dataset
        """
        with test_agent.vcr_context():
            records = [
                DatasetRecordRequest(
                    input_data={"prompt": "What is the capital of France?"},
                    expected_output={"answer": "Paris"},
                    metadata={"difficulty": "easy", "category": "geography"},
                ),
            ]

            create_request = DatasetCreateRequest(
                dataset_name="test-dataset-with-metadata",
                description="A test dataset with metadata",
                records=records,
            )
            dataset = test_library.llmobs_dataset_create(create_request)

            # Verify dataset was created
            assert dataset is not None
            assert dataset.dataset_id is not None
            assert len(dataset.records) == 1

            # Verify metadata is present
            record = dataset.records[0]
            assert record.get("metadata", {}).get("difficulty") == "easy"
            assert record.get("metadata", {}).get("category") == "geography"

            # Clean up
            delete_request = DatasetDeleteRequest(dataset_id=dataset.dataset_id)
            test_library.llmobs_dataset_delete(delete_request)

    def test_dataset_create_project_override(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test that a dataset can be created with a custom project name.

        Verifies that:
        1. A project_name can be specified during creation
        2. The dataset is associated with the specified project
        """
        with test_agent.vcr_context():
            create_request = DatasetCreateRequest(
                dataset_name="test-dataset-custom-project",
                description="A test dataset in a custom project",
                project_name="custom-project",
            )
            dataset = test_library.llmobs_dataset_create(create_request)

            # Verify dataset was created in the custom project
            assert dataset is not None
            assert dataset.dataset_id is not None
            assert dataset.project_name == "custom-project"

            # Clean up
            delete_request = DatasetDeleteRequest(dataset_id=dataset.dataset_id)
            test_library.llmobs_dataset_delete(delete_request)
