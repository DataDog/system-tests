import os
import pytest


@pytest.fixture
def llmobs_enabled() -> bool:
    return True


@pytest.fixture
def llmobs_ml_app() -> str | None:
    return "test-ml-app"


@pytest.fixture
def dd_service() -> str:
    return "test-service"


@pytest.fixture
def llmobs_override_origin() -> str | None:
    return None


@pytest.fixture
def llmobs_project_name() -> str | None:
    return None


@pytest.fixture
def library_env(
    llmobs_ml_app: str | None,
    dd_service: str,
    llmobs_override_origin: str | None,
    llmobs_project_name: str | None,
    *,
    llmobs_enabled: bool,
) -> dict[str, object]:
    env = {
        "DD_LLMOBS_ENABLED": llmobs_enabled,
        "DD_SERVICE": dd_service,
        "DD_API_KEY": os.getenv("DD_API_KEY", "test-api-key"),  # TODO: set these properly
        "DD_APP_KEY": os.getenv(
            "DD_APP_KEY", os.getenv("DD_APPLICATION_KEY", "test-app-key")
        ),  # TODO: set these properly
    }

    if llmobs_ml_app is not None:
        env["DD_LLMOBS_ML_APP"] = llmobs_ml_app

    if llmobs_project_name is not None:
        env["DD_LLMOBS_PROJECT_NAME"] = llmobs_project_name

    if llmobs_override_origin is not None:
        env["DD_LLMOBS_OVERRIDE_ORIGIN"] = llmobs_override_origin
        env["_DD_LLMOBS_OVERRIDE_ORIGIN"] = llmobs_override_origin  # required for Node.js

    return env


@pytest.fixture
def agent_env() -> dict[str, object]:
    return {
        "VCR_IGNORE_HEADERS": "content-security-policy",
    }
