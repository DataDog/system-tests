import subprocess
from pathlib import Path

import pytest

from utils.scripts.update_agent_version import (
    AUTOMATION_BRANCH,
    DOCKER_COMPOSE_PROVISION,
    GitHubApi,
    INSTALLER_PROVISION,
    automate_update,
    normalize_version,
    publish_update,
    run_automation,
    update_agent_version,
)

pytestmark = pytest.mark.scenario("TEST_THE_TEST")


def write_pins(root: Path) -> None:
    installer = root / INSTALLER_PROVISION
    installer.parent.mkdir(parents=True)
    installer.write_text(
        "remote-command: |\n"
        "    # Pin to 7.78.4 agent release. APMSP-3059\n"
        "    export DD_AGENT_MAJOR_VERSION=7\n"
        "    export DD_AGENT_MINOR_VERSION=78.4\n"
        "    echo install\n"
    )
    compose = root / DOCKER_COMPOSE_PROVISION
    compose.parent.mkdir(parents=True)
    compose.write_text(
        "services:\n"
        "  datadog:\n"
        "    # Pin to 7.78.4 agent release. APMSP-3059\n"
        "    image: gcr.io/datadoghq/agent:7.78.4\n"
    )


def test_update_agent_version_updates_both_ssi_pins(tmp_path: Path) -> None:
    write_pins(tmp_path)

    assert update_agent_version(tmp_path, "v7.82.3")
    assert "DD_AGENT_MINOR_VERSION=82.3" in (tmp_path / INSTALLER_PROVISION).read_text()
    assert "gcr.io/datadoghq/agent:7.82.3" in (tmp_path / DOCKER_COMPOSE_PROVISION).read_text()
    assert "updated automatically by APMSP-3752" in (tmp_path / INSTALLER_PROVISION).read_text()

    assert not update_agent_version(tmp_path, "7.82.3")


@pytest.mark.parametrize("version", ["8.0.0", "7.82", "7.82.3-rc.1", "latest"])
def test_normalize_version_rejects_unsupported_versions(version: str) -> None:
    with pytest.raises(ValueError, match="Expected a stable Agent 7 version"):
        normalize_version(version)


def test_update_agent_version_fails_when_a_pin_is_missing(tmp_path: Path) -> None:
    write_pins(tmp_path)
    (tmp_path / INSTALLER_PROVISION).write_text("remote-command: |\n    echo install\n")

    with pytest.raises(RuntimeError, match="exactly one Agent version pin"):
        update_agent_version(tmp_path, "7.82.3")


def test_automate_update_publishes_latest_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_pins(tmp_path)
    published: list[tuple[Path, str]] = []
    github = GitHubApi("token")
    monkeypatch.setattr("utils.scripts.update_agent_version.latest_agent_version", lambda _github: "7.82.3")
    monkeypatch.setattr(
        "utils.scripts.update_agent_version.publish_update",
        lambda root, version, _github, _env: published.append((root, version)),
    )

    assert automate_update(tmp_path, github, {})
    assert published == [(tmp_path, "7.82.3")]


def test_automate_update_skips_publish_when_current(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_pins(tmp_path)
    update_agent_version(tmp_path, "7.82.3")
    github = GitHubApi("token")
    monkeypatch.setattr(
        "utils.scripts.update_agent_version.publish_update",
        lambda _root, _version, _github, _env: pytest.fail("publish should not run"),
    )

    assert not automate_update(tmp_path, github, {}, "7.82.3")


@pytest.mark.parametrize("existing_pr", ["", "1234"])
def test_publish_update_creates_only_missing_pr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing_pr: str
) -> None:
    commands: list[list[str]] = []

    class FakeGitHubApi(GitHubApi):
        def __init__(self) -> None:
            super().__init__("token")
            self.calls: list[tuple[str, str]] = []

        def request(self, method: str, path: str, data: dict[str, object] | None = None) -> object:
            self.calls.append((method, path))
            if method == "GET":
                return [{"node_id": "PR_node_id"}] if existing_pr else []
            if path.endswith("/pulls"):
                return {"node_id": "PR_node_id"}
            assert path == "/graphql"
            assert data is not None
            return {"data": {}}

    def fake_run(
        _root: Path,
        args: list[str],
        *,
        capture_output: bool = False,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        assert env == {"GH_TOKEN": "token"}
        commands.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="" if capture_output else None)

    monkeypatch.setattr("utils.scripts.update_agent_version.run_command", fake_run)

    github = FakeGitHubApi()
    publish_update(tmp_path, "7.82.3", github, {"GH_TOKEN": "token"})

    assert ["git", "push", "--force", "--set-upstream", "origin", AUTOMATION_BRANCH] in commands
    assert not any(command[0] == "gh" for command in commands)
    assert any(method == "POST" and path.endswith("/pulls") for method, path in github.calls) is (not existing_pr)
    assert github.calls[-1] == ("POST", "/graphql")


def test_run_automation_revokes_token_after_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    def fake_run(
        _root: Path,
        args: list[str],
        *,
        capture_output: bool = False,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        assert env is None
        commands.append(args)
        stdout = "secret-token" if capture_output else ""
        return subprocess.CompletedProcess(args, 0, stdout=stdout)

    def fail_update(_root: Path, _github: GitHubApi, env: dict[str, str], _version: str | None) -> bool:
        assert env["GH_TOKEN"] == "secret-token"
        raise RuntimeError("publish failed")

    monkeypatch.setattr("utils.scripts.update_agent_version.run_command", fake_run)
    monkeypatch.setattr("utils.scripts.update_agent_version.automate_update", fail_update)

    with pytest.raises(RuntimeError, match="publish failed"):
        run_automation(tmp_path)

    assert commands[-1] == ["dd-octo-sts", "revoke", "-t", "secret-token"]


def test_run_automation_rejects_empty_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    def fake_run(
        _root: Path,
        args: list[str],
        *,
        capture_output: bool = False,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        assert env is None
        commands.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="" if capture_output else None)

    monkeypatch.setattr("utils.scripts.update_agent_version.run_command", fake_run)

    with pytest.raises(RuntimeError, match="empty GitHub token"):
        run_automation(tmp_path)

    assert not any(command[:2] == ["dd-octo-sts", "revoke"] for command in commands)
