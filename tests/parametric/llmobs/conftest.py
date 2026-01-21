import pytest


@pytest.fixture
def llmobs_enabled() -> bool:
    return True


@pytest.fixture
def llmobs_ml_app() -> str | None:
    return "test-ml-app"


@pytest.fixture
def llmobs_project_name() -> str:
    return "test-project"


@pytest.fixture
def dd_service() -> str:
    return "test-service"
