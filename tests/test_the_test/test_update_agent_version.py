import os
import subprocess
from pathlib import Path

from utils import pytest

from utils import scenarios
from utils.scripts.update_agent_version import (
    AGENT_VERSION_LOCK,
    AUTOMATION_BRANCH,
    GitHubApi,
    automate_update,
    enable_auto_merge,
    normalize_version,
    publish_update,
    revoke_token,
    run_automation,
    update_agent_version,
)


def write_lock(root: Path) -> None:
    lock = root / AGENT_VERSION_LOCK
    lock.parent.mkdir(parents=True)
    lock.write_text("# Pinned Agent version, updated automatically\nDD_AGENT_VERSION=7.78.4\n")


@scenarios.test_the_test
def test_update_agent_version_updates_lock(tmp_path: Path) -> None:
    write_lock(tmp_path)
    (tmp_path / AGENT_VERSION_LOCK).write_text("This content is replaced completely.\n")

    assert update_agent_version(tmp_path, "v8.0.1")
    assert (tmp_path / AGENT_VERSION_LOCK).read_text() == (
        "# Pinned Agent version, updated automatically\nDD_AGENT_VERSION=8.0.1\n"
    )

    assert not update_agent_version(tmp_path, "8.0.1")


@scenarios.test_the_test
@pytest.mark.parametrize("version", ["7.82", "7.82.3-rc.1", "latest"])
def test_normalize_version_rejects_unsupported_versions(version: str) -> None:
    with pytest.raises(ValueError, match="Expected a stable Agent version"):
        normalize_version(version)


@scenarios.test_the_test
def test_agent_version_consumers_load_lock() -> None:
    root = Path(__file__).resolve().parents[2]
    virtual_machine = root / "utils/build/virtual_machine"
    auto_inject = root / "utils/build/virtual_machine/provisions/auto-inject"

    lock_lines = (virtual_machine / "agent.lock").read_text().splitlines()
    assert lock_lines[0] == "# Pinned Agent version, updated automatically"
    assert len(lock_lines) == 2
    locked_version = lock_lines[1].removeprefix("DD_AGENT_VERSION=")
    assert lock_lines[1] == f"DD_AGENT_VERSION={normalize_version(locked_version)}"
    assert "agent:${DD_AGENT_VERSION}" in (auto_inject / "docker/docker-compose-agent-prod.yml").read_text()

    compose_path = "utils/build/virtual_machine/provisions/auto-inject/docker/docker-compose-agent-prod.yml"
    lock_path = "utils/build/virtual_machine/agent.lock"
    provision_root = virtual_machine
    compose_copy_points = [path for path in provision_root.rglob("*.yml") if compose_path in path.read_text()]
    assert compose_copy_points
    for copy_point in compose_copy_points:
        assert lock_path in copy_point.read_text()

    lock_consumers = (
        auto_inject / "auto-inject_installer_manual.yml",
        auto_inject / "repositories/autoinstall/execute_install_script.sh",
        root / "utils/build/virtual_machine/provisions/local-auto-inject-install-script/provision.yml",
        root / "utils/build/virtual_machine/weblogs/common/pull_agent_image.sh",
    )
    for consumer in lock_consumers:
        content = consumer.read_text()
        assert "agent.lock" in content
        assert "DD_AGENT_VERSION" in content
        assert "install_script_agent7.sh" not in content

    compose_launchers = (
        root / "utils/build/virtual_machine/weblogs/common/create_and_run_app_container.sh",
        root / "utils/build/virtual_machine/weblogs/common/create_and_run_app_multicontainer.sh",
        root / "utils/build/virtual_machine/weblogs/java/test-app-java-buildpack/"
        "test-app-java_docker_compose_run_buildpack.sh",
    )
    for launcher in compose_launchers:
        content = launcher.read_text()
        assert 'AGENT_LOCK="agent.lock"' in content
        assert '. "./${AGENT_LOCK}"' in content


@scenarios.test_the_test
def test_pull_agent_image_resolves_version_from_lock(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    (tmp_path / "agent.lock").write_text("DD_AGENT_VERSION=8.0.1\n")
    (tmp_path / "docker-compose-agent-prod.yml").write_text(
        "services:\n  datadog:\n    image: gcr.io/datadoghq/agent:${DD_AGENT_VERSION}\n"
    )

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    call_log = tmp_path / "sudo.log"
    fake_sudo = fake_bin / "sudo"
    fake_sudo.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALL_LOG"\n')
    fake_sudo.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "CALL_LOG": str(call_log),
            "DOCKER_PULL_MAX_RETRIES": "1",
            "PATH": f"{fake_bin}:{env['PATH']}",
        }
    )

    subprocess.run(
        ["bash", str(root / "utils/build/virtual_machine/weblogs/common/pull_agent_image.sh")],
        cwd=tmp_path,
        check=True,
        env=env,
    )

    assert call_log.read_text() == "docker pull gcr.io/datadoghq/agent:8.0.1\n"


@scenarios.test_the_test
def test_automate_update_publishes_latest_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_lock(tmp_path)
    published: list[tuple[Path, str]] = []
    github = GitHubApi("token")
    monkeypatch.setattr("utils.scripts.update_agent_version.latest_agent_version", lambda _github: "8.0.1")
    monkeypatch.setattr(
        "utils.scripts.update_agent_version.publish_update",
        lambda root, version, _github, _env: published.append((root, version)),
    )

    assert automate_update(tmp_path, github, {})
    assert published == [(tmp_path, "8.0.1")]


@scenarios.test_the_test
@pytest.mark.parametrize("version", ["7.82.3", "7.82.2", "6.53.4"])
def test_automate_update_skips_publish_when_not_newer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: str
) -> None:
    write_lock(tmp_path)
    update_agent_version(tmp_path, "7.82.3")
    github = GitHubApi("token")
    monkeypatch.setattr(
        "utils.scripts.update_agent_version.publish_update",
        lambda _root, _version, _github, _env: pytest.fail("publish should not run"),
    )

    assert not automate_update(tmp_path, github, {}, version)
    assert (tmp_path / AGENT_VERSION_LOCK).read_text().endswith("DD_AGENT_VERSION=7.82.3\n")


@scenarios.test_the_test
@pytest.mark.parametrize("existing_pr", ["", "1234"])
def test_publish_update_creates_only_missing_pr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing_pr: str
) -> None:
    commands: list[list[str]] = []

    class FakeGitHubApi(GitHubApi):
        def __init__(self) -> None:
            super().__init__("token")
            self.calls: list[tuple[str, str]] = []
            self.descriptions: list[dict[str, object]] = []

        def request(self, method: str, path: str, data: dict[str, object] | None = None) -> object:
            self.calls.append((method, path))
            if method == "GET":
                return [{"node_id": "PR_node_id", "number": int(existing_pr)}] if existing_pr else []
            if path == "/graphql":
                assert data is not None
                # GitHub rejects enabling auto-merge on a PR that already has it, i.e. on every refresh.
                if existing_pr:
                    return {
                        "data": {"enablePullRequestAutoMerge": None},
                        "errors": [{"message": "Pull request Auto merge is already enabled."}],
                    }
                return {"data": {"enablePullRequestAutoMerge": {"pullRequest": {"number": 42}}}}
            assert data is not None
            self.descriptions.append(data)
            return {"node_id": "PR_node_id"}

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

    assert ["git", "add", str(AGENT_VERSION_LOCK)] in commands
    assert ["git", "push", "--force", "--set-upstream", "origin", AUTOMATION_BRANCH] in commands
    assert not any(command[0] == "gh" for command in commands)
    assert any(method == "POST" and path.endswith("/pulls") for method, path in github.calls) is (not existing_pr)
    if existing_pr:
        assert ("PATCH", f"/repos/DataDog/system-tests/pulls/{existing_pr}") in github.calls
    # Whether it is created or refreshed, the PR describes the version that was just pushed.
    assert [description["title"] for description in github.descriptions] == ["Update Agent to 7.82.3"]
    assert github.calls[-1] == ("POST", "/graphql")


def fake_github(result: object) -> GitHubApi:
    class FakeGitHubApi(GitHubApi):
        def request(self, method: str, path: str, data: dict[str, object] | None = None) -> object:  # noqa: ARG002
            return result

    return FakeGitHubApi("token")


@scenarios.test_the_test
@pytest.mark.parametrize(
    "result",
    [
        {"errors": [{"message": "Pull request Auto merge is not allowed for this repository"}]},
        {
            "errors": [
                {"message": "Pull request Auto merge is already enabled."},
                {"message": "Something else went wrong"},
            ]
        },
    ],
)
def test_enable_auto_merge_reports_real_failures(result: object) -> None:
    with pytest.raises(RuntimeError, match="failed to enable pull request auto-merge"):
        enable_auto_merge(fake_github(result), "PR_node_id")


@scenarios.test_the_test
@pytest.mark.parametrize("result", [[], {"errors": "boom"}])
def test_enable_auto_merge_rejects_invalid_responses(result: object) -> None:
    with pytest.raises(TypeError, match="invalid auto-merge response"):
        enable_auto_merge(fake_github(result), "PR_node_id")


@scenarios.test_the_test
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


@scenarios.test_the_test
def test_revoke_token_hides_token_and_command_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    token = "secret-token"

    def fail_run(
        _root: Path,
        args: list[str],
        *,
        capture_output: bool = False,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        assert capture_output
        assert env is None
        raise subprocess.CalledProcessError(
            1,
            args,
            output=f"stdout containing {token}",
            stderr=f"stderr containing {token}",
        )

    monkeypatch.setattr("utils.scripts.update_agent_version.run_command", fail_run)

    with pytest.raises(RuntimeError, match="token revocation failed with exit code 1") as error:
        revoke_token(tmp_path, token)

    captured = capsys.readouterr()
    assert token not in str(error.value)
    assert captured.out == ""
    assert captured.err == ""


@scenarios.test_the_test
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
