"""Shared fixtures for LLM Observability parametric tests."""

import pytest


@pytest.fixture
def llmobs_enabled() -> bool:
    """Enable LLM Observability for tests."""
    return True


@pytest.fixture
def llmobs_ml_app() -> str | None:
    """Default ML app name for LLM Observability tests."""
    return "test-ml-app"


@pytest.fixture
def llmobs_project_name() -> str:
    """Default project name for LLM Observability DNE tests."""
    return "test-project"


@pytest.fixture
def dd_service() -> str:
    """Default service name for tests."""
    return "test-service"
