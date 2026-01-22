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


@pytest.fixture
def library_env(llmobs_ml_app: str | None, dd_service: str, *, llmobs_enabled: bool) -> dict[str, object]:
    env = {
        "DD_LLMOBS_ENABLED": llmobs_enabled,
        "DD_SERVICE": dd_service,
    }
    if llmobs_ml_app is not None:
        env["DD_LLMOBS_ML_APP"] = llmobs_ml_app
    return env
