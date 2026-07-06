import pytest

from utils._context.component_version import ComponentVersion, Version
from utils.nodejs_runtime import (
    filter_nodejs_runtimes_for_ci,
    infer_minimum_nodejs_runtime_for_ci,
    is_supported_nodejs_runtime,
    select_nodejs_aws_weblog_for_ci,
)


def _clear_nodejs_runtime_env(monkeypatch: pytest.MonkeyPatch):
    for env_name in [
        "SYSTEM_TESTS_NODEJS_MIN_RUNTIME",
        "DD_NODEJS_RUNTIME_VERSION",
        "DD_INSTALLER_LIBRARY_VERSION",
        "DD_INSTALLER_LIBRARY_VERSION_NODEJS",
        "CI_COMMIT_BRANCH",
        "CI_COMMIT_REF_NAME",
        "CI_MERGE_REQUEST_SOURCE_BRANCH_NAME",
        "CI_COMMIT_TAG",
        "GITHUB_REF_NAME",
        "GITHUB_HEAD_REF",
    ]:
        monkeypatch.delenv(env_name, raising=False)


def test_nodejs_runtime_support_depends_on_library_major():
    assert is_supported_nodejs_runtime(ComponentVersion("nodejs", "5.0.0"), Version("18.20"))
    assert is_supported_nodejs_runtime(ComponentVersion("nodejs", "5.0.0"), Version("20.18"))
    assert not is_supported_nodejs_runtime(ComponentVersion("nodejs", "6.0.0-pre"), Version("20.18"))
    assert is_supported_nodejs_runtime(ComponentVersion("nodejs", "6.0.0-pre"), Version("22.0"))


def test_infer_minimum_nodejs_runtime_for_ci_from_library_version(monkeypatch: pytest.MonkeyPatch):
    _clear_nodejs_runtime_env(monkeypatch)

    assert infer_minimum_nodejs_runtime_for_ci("5.0.0") == "18.0"
    assert infer_minimum_nodejs_runtime_for_ci("6.0.0-pre") == "22.0"


def test_infer_minimum_nodejs_runtime_for_ci_from_ref(monkeypatch: pytest.MonkeyPatch):
    _clear_nodejs_runtime_env(monkeypatch)

    monkeypatch.setenv("CI_COMMIT_BRANCH", "master")
    assert infer_minimum_nodejs_runtime_for_ci("pipeline-123") == "22.0"

    monkeypatch.setenv("CI_COMMIT_BRANCH", "v5.67.0-proposal")
    assert infer_minimum_nodejs_runtime_for_ci("pipeline-123") == "18.0"

    monkeypatch.setenv("CI_COMMIT_BRANCH", "v6.0.0-proposal")
    assert infer_minimum_nodejs_runtime_for_ci("pipeline-123") == "22.0"

    monkeypatch.delenv("CI_COMMIT_BRANCH")
    monkeypatch.setenv("CI_COMMIT_REF_NAME", "refs/heads/v5.68.0")
    assert infer_minimum_nodejs_runtime_for_ci("pipeline-123") == "18.0"


def test_filter_nodejs_runtimes_for_ci(monkeypatch: pytest.MonkeyPatch):
    _clear_nodejs_runtime_env(monkeypatch)

    monkeypatch.setenv("CI_COMMIT_BRANCH", "master")
    runtimes = [
        {"version_id": "JS1820", "version": "18.20"},
        {"version_id": "JS2018", "version": "20.18"},
        {"version_id": "JS2200", "version": "22.0"},
        {"version_id": "JS2300", "version": "23.0"},
    ]

    assert filter_nodejs_runtimes_for_ci(runtimes) == [
        {"version_id": "JS2200", "version": "22.0"},
        {"version_id": "JS2300", "version": "23.0"},
    ]


def test_select_nodejs_aws_weblog_for_ci(monkeypatch: pytest.MonkeyPatch):
    _clear_nodejs_runtime_env(monkeypatch)

    monkeypatch.setenv("CI_COMMIT_BRANCH", "master")
    assert select_nodejs_aws_weblog_for_ci("test-app-nodejs") == "test-app-nodejs-22"
    assert select_nodejs_aws_weblog_for_ci("test-app-nodejs-container") == "test-app-nodejs-container-22"
    assert select_nodejs_aws_weblog_for_ci("test-app-nodejs-esm") == "test-app-nodejs-esm-22"
    assert select_nodejs_aws_weblog_for_ci("test-app-nodejs-unsupported-defaults") == (
        "test-app-nodejs-unsupported-defaults"
    )
