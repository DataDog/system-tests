import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Mark all llm_observability tests as xfail when generating cassettes."""
    if config.option.generate_cassettes:
        for item in items:
            item.add_marker(
                pytest.mark.xfail(
                    reason="Generating cassettes - test assertions are not evaluated",
                    strict=False,
                )
            )


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
def dd_api_key() -> str | None:
    return None


@pytest.fixture
def dd_app_key() -> str | None:
    return None


@pytest.fixture
def library_env(
    llmobs_ml_app: str | None,
    dd_service: str,
    llmobs_override_origin: str | None,
    llmobs_project_name: str | None,
    dd_api_key: str | None,
    dd_app_key: str | None,
    *,
    llmobs_enabled: bool,
) -> dict[str, object]:
    env: dict[str, object] = {
        "DD_LLMOBS_ENABLED": llmobs_enabled,
        "DD_SERVICE": dd_service,
    }

    if dd_api_key is not None:
        env["DD_API_KEY"] = dd_api_key

    if dd_app_key is not None:
        env["DD_APP_KEY"] = dd_app_key

    if llmobs_ml_app is not None:
        env["DD_LLMOBS_ML_APP"] = llmobs_ml_app

    if llmobs_project_name is not None:
        env["DD_LLMOBS_PROJECT_NAME"] = llmobs_project_name

    if llmobs_override_origin is not None:
        env["DD_LLMOBS_OVERRIDE_ORIGIN"] = llmobs_override_origin
        env["_DD_LLMOBS_OVERRIDE_ORIGIN"] = llmobs_override_origin  # required for Node.js

    return env


@pytest.fixture
def agent_env(request: pytest.FixtureRequest) -> dict[str, object]:
    agent_env: dict[str, object] = {
        "VCR_IGNORE_HEADERS": "content-security-policy",
    }

    if not request.config.option.generate_cassettes:
        agent_env["VCR_CI_MODE"] = "1"

    return agent_env
