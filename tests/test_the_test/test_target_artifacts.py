from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import requests

from utils import scenarios
from utils.const import COMPONENT_GROUPS
from utils.target_artifacts.models import (
    ArtifactResolver,
    BranchReference,
    GitHubActionsArtifactReference,
    GitHubReleaseReference,
    LiteralValue,
    ModuleVersion,
    OciImageReference,
    ReleaseAsset,
    ResolvedArtifactInput,
    TargetArtifactError,
)
from utils.target_artifacts.orchestrator import MANIFEST_FILENAME, load_target_environment, stage_target
from utils.target_artifacts.resolvers import (
    CratesLatestResolver,
    EnvResolver,
    GitHubActionsArtifactResolver,
    GitHubBranchResolver,
    GitHubLatestReleaseResolver,
    GoModuleLatestResolver,
    NpmLatestResolver,
    OciDigestResolver,
    PypiLatestResolver,
    RubygemsLatestResolver,
)

if TYPE_CHECKING:
    from collections.abc import Callable

SHA = "1" * 40
DIGEST = "sha256:" + ("2" * 64)
OTHER_SHA = "3" * 40


class StubResponse:
    def __init__(
        self,
        payload: object,
        *,
        status_error: requests.RequestException | None = None,
        json_error: ValueError | None = None,
    ) -> None:
        self.payload = payload
        self.status_error = status_error
        self.json_error = json_error

    def raise_for_status(self) -> None:
        if self.status_error is not None:
            raise self.status_error

    def json(self) -> object:
        if self.json_error is not None:
            raise self.json_error
        return self.payload


def _stub_get_json(
    monkeypatch: pytest.MonkeyPatch,
    payloads: dict[str, dict[str, Any]] | Callable[[str, dict[str, str]], dict[str, Any]],
) -> list[tuple[str, dict[str, str]]]:
    calls: list[tuple[str, dict[str, str]]] = []

    def fake_get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
        calls.append((url, dict(headers)))
        if callable(payloads):
            return payloads(url, headers)
        return payloads[url]

    monkeypatch.setattr("utils.target_artifacts.resolvers._get_json", fake_get_json)
    return calls


def _completed_process(
    args: list[str],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


class FakeResolver:
    def resolve(self, artifact_resolver: ArtifactResolver, env: dict[str, str]) -> ResolvedArtifactInput:
        if isinstance(artifact_resolver, EnvResolver):
            return LiteralValue(
                name=artifact_resolver.name,
                value=env.get(artifact_resolver.variable_name, artifact_resolver.default_value),
            )
        if isinstance(artifact_resolver, GitHubBranchResolver):
            return BranchReference(
                name=artifact_resolver.name,
                repository=artifact_resolver.repository,
                branch=env.get(artifact_resolver.variable_name, artifact_resolver.default_value),
                sha=SHA,
            )
        if isinstance(artifact_resolver, GitHubLatestReleaseResolver):
            return GitHubReleaseReference(
                name=artifact_resolver.name,
                repository=artifact_resolver.repository,
                tag_name="v1.2.3",
            )
        if isinstance(artifact_resolver, GitHubActionsArtifactResolver):
            return GitHubActionsArtifactReference(
                name=artifact_resolver.name,
                repository=artifact_resolver.repository,
                workflow=artifact_resolver.workflow,
                branch=env.get(artifact_resolver.variable_name, artifact_resolver.default_value),
                commit_sha=SHA,
                run_id=123,
                run_url="https://github.example/run",
                artifact_id=456,
                artifact_name=artifact_resolver.artifact_name,
                archive_download_url="https://github.example/artifact.zip",
            )
        if isinstance(artifact_resolver, OciDigestResolver):
            image = env.get(
                artifact_resolver.variable_name,
                artifact_resolver.image or artifact_resolver.default_value,
            )
            last_slash = image.rfind("/")
            last_colon = image.rfind(":")
            repository = image[:last_colon] if last_colon > last_slash else image
            return OciImageReference(
                name=artifact_resolver.name,
                image=image,
                digest=DIGEST,
                reference=f"{repository}@{DIGEST}",
            )
        if isinstance(
            artifact_resolver,
            (NpmLatestResolver, PypiLatestResolver, RubygemsLatestResolver, CratesLatestResolver),
        ):
            return ModuleVersion(name=artifact_resolver.name, module=artifact_resolver.package, version="1.2.3")
        if isinstance(artifact_resolver, GoModuleLatestResolver):
            return ModuleVersion(name=artifact_resolver.name, module=artifact_resolver.module, version="v1.2.3")
        raise AssertionError(f"Unhandled input resolver: {type(artifact_resolver).__name__}")


def _write_target_module(repo_root: Path, body: str) -> None:
    target_dir = repo_root / "utils" / "build" / "docker" / "fake"
    target_dir.mkdir(parents=True)
    (target_dir / "artifact.py").write_text(body, encoding="utf-8")


def _manifest_entries(binaries_dir: Path) -> dict[str, object]:
    manifest = json.loads((binaries_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    return manifest["entries"]


@scenarios.test_the_test
class Test_TargetArtifactStaging:
    def test_custom_environment_is_noop(self, tmp_path: Path) -> None:
        binaries_dir = tmp_path / "binaries"

        stage_target(
            "does-not-exist",
            "custom",
            repo_root=tmp_path,
            binaries_dir=binaries_dir,
            process_env={},
        )

        assert not binaries_dir.exists()

    def test_dotenv_values_are_loaded_and_process_environment_wins(self, tmp_path: Path) -> None:
        _write_target_module(
            tmp_path,
            """
from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.resolvers import EnvResolver

class Dev:
    def artifact_inputs(self, env):
        return (EnvResolver(name="value", variable_name="STAGED_VALUE", default_value="default"),)

    def artifact_entries(self, resolved_inputs):
        return (text_entry("value", resolved_inputs["value"].value),)

class Prod(Dev):
    pass
""",
        )
        (tmp_path / ".env").write_text("STAGED_VALUE=dotenv\n", encoding="utf-8")

        stage_target(
            "fake",
            "dev",
            repo_root=tmp_path,
            binaries_dir=tmp_path / "binaries",
            process_env={"STAGED_VALUE": "process"},
        )

        assert (tmp_path / "binaries" / "value").read_text(encoding="utf-8") == "process\n"

    def test_manifest_refreshes_owned_files_and_preserves_other_targets(self, tmp_path: Path) -> None:
        module_path = tmp_path / "utils" / "build" / "docker" / "fake"
        module_path.mkdir(parents=True)
        artifact_module = module_path / "artifact.py"
        artifact_module.write_text(
            """
from utils.target_artifacts.entry_helpers import text_entry

class Dev:
    def artifact_inputs(self, env):
        return ()

    def artifact_entries(self, resolved_inputs):
        return (text_entry("kept", "one"), text_entry("stale", "old"))

class Prod:
    def artifact_inputs(self, env):
        return ()

    def artifact_entries(self, resolved_inputs):
        return (text_entry("kept", "two"),)
""",
            encoding="utf-8",
        )
        other_module = tmp_path / "utils" / "build" / "docker" / "other" / "artifact.py"
        other_module.parent.mkdir(parents=True)
        other_module.write_text(
            """
from utils.target_artifacts.entry_helpers import text_entry

class Dev:
    def artifact_inputs(self, env):
        return ()

    def artifact_entries(self, resolved_inputs):
        return (text_entry("other", "target"),)

class Prod(Dev):
    pass
""",
            encoding="utf-8",
        )

        binaries_dir = tmp_path / "binaries"
        stage_target("fake", "dev", repo_root=tmp_path, binaries_dir=binaries_dir)
        stage_target("other", "dev", repo_root=tmp_path, binaries_dir=binaries_dir)
        stage_target("fake", "prod", repo_root=tmp_path, binaries_dir=binaries_dir)

        assert (binaries_dir / "kept").read_text(encoding="utf-8") == "two\n"
        assert not (binaries_dir / "stale").exists()
        assert (binaries_dir / "other").read_text(encoding="utf-8") == "target\n"
        assert set(_manifest_entries(binaries_dir)) == {"kept", "other"}

    def test_unowned_file_is_not_overwritten(self, tmp_path: Path) -> None:
        _write_target_module(
            tmp_path,
            """
from utils.target_artifacts.entry_helpers import text_entry

class Dev:
    def artifact_inputs(self, env):
        return ()

    def artifact_entries(self, resolved_inputs):
        return (text_entry("manual", "generated"),)

class Prod(Dev):
    pass
""",
        )
        binaries_dir = tmp_path / "binaries"
        binaries_dir.mkdir()
        (binaries_dir / "manual").write_text("user\n", encoding="utf-8")

        with pytest.raises(Exception, match="Refusing to overwrite unowned artifact entry 'manual'"):
            stage_target("fake", "dev", repo_root=tmp_path, binaries_dir=binaries_dir)

        assert (binaries_dir / "manual").read_text(encoding="utf-8") == "user\n"

    def test_github_release_resolver_wraps_request_failures(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fail_get(*_args: object, **_kwargs: object) -> object:
            raise requests.ConnectionError("network unavailable")

        monkeypatch.setattr("utils.target_artifacts.resolvers.requests.get", fail_get)
        resolver = GitHubLatestReleaseResolver(name="release", repository="DataDog/dd-trace-py")

        with pytest.raises(TargetArtifactError, match="Unable to resolve artifact metadata"):
            resolver.resolve({})

    def test_env_resolver_resolves_env_input(self) -> None:
        resolver = EnvResolver(name="value", variable_name="STAGED_VALUE", default_value="default")

        resolved = resolver.resolve({"STAGED_VALUE": "from-env"})

        assert resolved == LiteralValue(name="value", value="from-env")

    @pytest.mark.parametrize(
        ("resolver_type", "resolved_type"),
        [
            (EnvResolver, LiteralValue.__name__),
            (GitHubBranchResolver, BranchReference.__name__),
            (GitHubLatestReleaseResolver, GitHubReleaseReference.__name__),
            (GitHubActionsArtifactResolver, GitHubActionsArtifactReference.__name__),
            (OciDigestResolver, OciImageReference.__name__),
            (NpmLatestResolver, ModuleVersion.__name__),
            (PypiLatestResolver, ModuleVersion.__name__),
            (RubygemsLatestResolver, ModuleVersion.__name__),
            (CratesLatestResolver, ModuleVersion.__name__),
            (GoModuleLatestResolver, ModuleVersion.__name__),
        ],
    )
    def test_artifact_resolver_docstring_names_resolved_input_type(
        self,
        resolver_type: type[ArtifactResolver],
        resolved_type: str,
    ) -> None:
        assert resolver_type.__doc__ is not None
        assert resolved_type in resolver_type.__doc__


@scenarios.test_the_test
class Test_TargetArtifactResolvers:
    def test_github_requests_include_auth_header_when_token_is_provided(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[tuple[str, dict[str, str], int]] = []

        def fake_get(url: str, *, headers: dict[str, str], timeout: int) -> StubResponse:
            calls.append((url, dict(headers), timeout))
            return StubResponse({"tag_name": "v1.2.3"})

        monkeypatch.setattr("utils.target_artifacts.resolvers.requests.get", fake_get)

        resolved = GitHubLatestReleaseResolver(name="release", repository="DataDog/example").resolve(
            {"GITHUB_TOKEN": "secret-token"},
        )

        assert resolved.tag_name == "v1.2.3"
        assert calls == [
            (
                "https://api.github.com/repos/DataDog/example/releases/latest",
                {
                    "Accept": "application/vnd.github.v3+json",
                    "Authorization": "Bearer secret-token",
                },
                30,
            ),
        ]

    def test_get_json_wraps_non_json_payloads(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_get(_url: str, *, headers: dict[str, str], timeout: int) -> StubResponse:
            assert headers == {"Accept": "application/vnd.github.v3+json"}
            assert timeout == 30
            return StubResponse({}, json_error=ValueError("invalid json"))

        monkeypatch.setattr("utils.target_artifacts.resolvers.requests.get", fake_get)
        resolver = GitHubLatestReleaseResolver(name="release", repository="DataDog/example")

        with pytest.raises(TargetArtifactError, match="Unable to parse artifact metadata"):
            resolver.resolve({})

    def test_github_branch_resolver_accepts_full_sha_without_network(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fail_get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
            raise AssertionError(f"Unexpected GitHub request to {url} with {headers}")

        monkeypatch.setattr("utils.target_artifacts.resolvers._get_json", fail_get_json)
        resolver = GitHubBranchResolver(
            name="library_branch",
            repository="DataDog/dd-trace-py",
            variable_name="LIBRARY_TARGET_BRANCH",
        )

        resolved = resolver.resolve({"LIBRARY_TARGET_BRANCH": SHA})

        assert resolved == BranchReference(
            name="library_branch",
            repository="DataDog/dd-trace-py",
            branch=SHA,
            sha=SHA,
        )

    def test_github_branch_resolver_resolves_quoted_branch_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        branch = "feature/space branch"
        expected_url = "https://api.github.com/repos/DataDog/dd-trace-py/branches/feature%2Fspace%20branch"
        calls = _stub_get_json(
            monkeypatch,
            {
                expected_url: {
                    "commit": {
                        "sha": OTHER_SHA,
                    },
                },
            },
        )
        resolver = GitHubBranchResolver(
            name="library_branch",
            repository="DataDog/dd-trace-py",
            variable_name="LIBRARY_TARGET_BRANCH",
        )

        resolved = resolver.resolve({"GITHUB_TOKEN": "secret-token", "LIBRARY_TARGET_BRANCH": branch})

        assert resolved == BranchReference(
            name="library_branch",
            repository="DataDog/dd-trace-py",
            branch=branch,
            sha=OTHER_SHA,
        )
        assert calls == [
            (
                expected_url,
                {
                    "Accept": "application/vnd.github.v3+json",
                    "Authorization": "Bearer secret-token",
                },
            ),
        ]

    def test_github_branch_resolver_rejects_missing_branch(self) -> None:
        resolver = GitHubBranchResolver(name="library_branch", repository="DataDog/dd-trace-py")

        with pytest.raises(TargetArtifactError, match="Missing branch for input 'library_branch'"):
            resolver.resolve({})

    def test_github_branch_resolver_rejects_invalid_sha(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_get_json(
            monkeypatch,
            {
                "https://api.github.com/repos/DataDog/dd-trace-py/branches/main": {
                    "commit": {
                        "sha": "not-a-sha",
                    },
                },
            },
        )
        resolver = GitHubBranchResolver(
            name="library_branch",
            repository="DataDog/dd-trace-py",
            default_value="main",
        )

        with pytest.raises(TargetArtifactError, match="did not resolve to a commit SHA"):
            resolver.resolve({})

    def test_github_latest_release_resolver_includes_assets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_get_json(
            monkeypatch,
            {
                "https://api.github.com/repos/DataDog/dd-trace-java/releases/latest": {
                    "tag_name": "v1.2.3",
                    "assets": [
                        {
                            "name": "dd-java-agent.jar",
                            "browser_download_url": "https://github.example/dd-java-agent.jar",
                        },
                    ],
                },
            },
        )
        resolver = GitHubLatestReleaseResolver(
            name="release",
            repository="DataDog/dd-trace-java",
            include_assets=True,
        )

        resolved = resolver.resolve({})

        assert resolved == GitHubReleaseReference(
            name="release",
            repository="DataDog/dd-trace-java",
            tag_name="v1.2.3",
            assets=(
                ReleaseAsset(
                    name="dd-java-agent.jar",
                    browser_download_url="https://github.example/dd-java-agent.jar",
                ),
            ),
        )

    def test_github_latest_release_resolver_rejects_missing_assets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_get_json(
            monkeypatch,
            {
                "https://api.github.com/repos/DataDog/dd-trace-java/releases/latest": {
                    "tag_name": "v1.2.3",
                },
            },
        )
        resolver = GitHubLatestReleaseResolver(
            name="release",
            repository="DataDog/dd-trace-java",
            include_assets=True,
        )

        with pytest.raises(TargetArtifactError, match="did not include assets"):
            resolver.resolve({})

    def test_github_actions_artifact_resolver_selects_matching_artifact(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        expected_runs_url = (
            "https://api.github.com/repos/DataDog/httpd-datadog/actions/workflows/dev.yml/runs"
            "?branch=feature%2Fbranch&status=completed&per_page=100"
        )
        expected_artifacts_url = "https://api.github.example/runs/123/artifacts?per_page=100"
        calls = _stub_get_json(
            monkeypatch,
            {
                expected_runs_url: {
                    "workflow_runs": [
                        {
                            "conclusion": "failure",
                        },
                        {
                            "conclusion": "success",
                            "artifacts_url": "https://api.github.example/runs/123/artifacts",
                            "head_sha": SHA,
                            "id": 123,
                            "html_url": "https://github.example/DataDog/httpd-datadog/actions/runs/123",
                        },
                    ],
                },
                expected_artifacts_url: {
                    "artifacts": [
                        {
                            "id": 456,
                            "name": "logs",
                            "archive_download_url": "https://github.example/logs.zip",
                        },
                        {
                            "id": 789,
                            "name": "mod_datadog_artifact.zip",
                            "archive_download_url": "https://github.example/mod_datadog_artifact.zip",
                        },
                    ],
                },
            },
        )
        resolver = GitHubActionsArtifactResolver(
            name="workflow_artifact",
            repository="DataDog/httpd-datadog",
            workflow="dev.yml",
            artifact_name="mod_datadog_artifact",
            variable_name="LIBRARY_TARGET_BRANCH",
        )

        resolved = resolver.resolve({"LIBRARY_TARGET_BRANCH": "feature/branch"})

        assert resolved == GitHubActionsArtifactReference(
            name="workflow_artifact",
            repository="DataDog/httpd-datadog",
            workflow="dev.yml",
            branch="feature/branch",
            commit_sha=SHA,
            run_id=123,
            run_url="https://github.example/DataDog/httpd-datadog/actions/runs/123",
            artifact_id=789,
            artifact_name="mod_datadog_artifact.zip",
            archive_download_url="https://github.example/mod_datadog_artifact.zip",
        )
        assert [url for url, _headers in calls] == [expected_runs_url, expected_artifacts_url]

    def test_github_actions_artifact_resolver_errors_when_only_failed_runs_exist(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_get_json(
            monkeypatch,
            {
                "https://api.github.com/repos/DataDog/httpd-datadog/actions/workflows/dev.yml/runs"
                "?branch=main&status=completed&per_page=100": {
                    "workflow_runs": [
                        {
                            "conclusion": "failure",
                        },
                    ],
                },
            },
        )
        resolver = GitHubActionsArtifactResolver(
            name="workflow_artifact",
            repository="DataDog/httpd-datadog",
            workflow="dev.yml",
            artifact_name="mod_datadog_artifact",
            default_value="main",
        )

        with pytest.raises(TargetArtifactError, match="No completed workflow run found"):
            resolver.resolve({})

    def test_github_actions_artifact_resolver_errors_when_artifact_is_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_get_json(
            monkeypatch,
            {
                "https://api.github.com/repos/DataDog/httpd-datadog/actions/workflows/dev.yml/runs"
                "?branch=main&status=completed&per_page=100": {
                    "workflow_runs": [
                        {
                            "conclusion": "success",
                            "artifacts_url": "https://api.github.example/runs/123/artifacts",
                            "head_sha": SHA,
                            "id": 123,
                            "html_url": "https://github.example/DataDog/httpd-datadog/actions/runs/123",
                        },
                    ],
                },
                "https://api.github.example/runs/123/artifacts?per_page=100": {
                    "artifacts": [
                        {
                            "id": 456,
                            "name": "logs",
                            "archive_download_url": "https://github.example/logs.zip",
                        },
                    ],
                },
            },
        )
        resolver = GitHubActionsArtifactResolver(
            name="workflow_artifact",
            repository="DataDog/httpd-datadog",
            workflow="dev.yml",
            artifact_name="mod_datadog_artifact",
            default_value="main",
        )

        with pytest.raises(TargetArtifactError, match="No artifact containing 'mod_datadog_artifact' found"):
            resolver.resolve({})

    def test_oci_digest_resolver_accepts_pinned_digest_without_docker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fail_run(
            args: list[str], *, capture_output: bool, check: bool, text: bool
        ) -> subprocess.CompletedProcess[str]:
            raise AssertionError(f"Unexpected docker invocation: {args}, {capture_output}, {check}, {text}")

        monkeypatch.setattr("utils.target_artifacts.resolvers.subprocess.run", fail_run)
        image = f"registry.example.com/team/app@{DIGEST}"
        resolver = OciDigestResolver(name="image", image=image)

        resolved = resolver.resolve({})

        assert resolved == OciImageReference(
            name="image",
            image=image,
            digest=DIGEST,
            reference=image,
        )

    def test_oci_digest_resolver_builds_digest_reference_for_registry_with_port(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        image = "registry.example.com:5000/team/app:latest"

        def fake_run(
            args: list[str],
            *,
            capture_output: bool,
            check: bool,
            text: bool,
        ) -> subprocess.CompletedProcess[str]:
            assert args == ["docker", "buildx", "imagetools", "inspect", image]
            assert capture_output is True
            assert check is False
            assert text is True
            return _completed_process(args, stdout=f"Name: {image}\nDigest: {DIGEST}\n")

        monkeypatch.setattr("utils.target_artifacts.resolvers.subprocess.run", fake_run)
        resolver = OciDigestResolver(name="image", image=image)

        resolved = resolver.resolve({})

        assert resolved == OciImageReference(
            name="image",
            image=image,
            digest=DIGEST,
            reference=f"registry.example.com:5000/team/app@{DIGEST}",
        )

    @pytest.mark.parametrize(
        ("run_result", "match"),
        [
            (FileNotFoundError(), "docker was not found"),
            (_completed_process([], returncode=1, stderr="denied"), "denied"),
            (_completed_process([], stdout="Name: registry.example.com/app\n"), "Unable to find OCI digest"),
        ],
    )
    def test_oci_digest_resolver_wraps_docker_failures(
        self,
        monkeypatch: pytest.MonkeyPatch,
        run_result: subprocess.CompletedProcess[str] | FileNotFoundError,
        match: str,
    ) -> None:
        def fake_run(
            args: list[str],
            *,
            capture_output: bool,
            check: bool,
            text: bool,
        ) -> subprocess.CompletedProcess[str]:
            assert capture_output is True
            assert check is False
            assert text is True
            if isinstance(run_result, FileNotFoundError):
                raise run_result
            return _completed_process(
                args, returncode=run_result.returncode, stdout=run_result.stdout, stderr=run_result.stderr
            )

        monkeypatch.setattr("utils.target_artifacts.resolvers.subprocess.run", fake_run)
        resolver = OciDigestResolver(name="image", image="registry.example.com/app:latest")

        with pytest.raises(TargetArtifactError, match=match):
            resolver.resolve({})

    @pytest.mark.parametrize(
        ("resolver", "payload", "expected"),
        [
            (
                NpmLatestResolver(name="package", package="@datadog/browser-core"),
                {"version": "1.2.3"},
                ModuleVersion(name="package", module="@datadog/browser-core", version="1.2.3"),
            ),
            (
                PypiLatestResolver(name="package", package="ddtrace"),
                {"info": {"version": "2.3.4"}},
                ModuleVersion(name="package", module="ddtrace", version="2.3.4"),
            ),
            (
                RubygemsLatestResolver(name="package", package="datadog"),
                {"version": "3.4.5"},
                ModuleVersion(name="package", module="datadog", version="3.4.5"),
            ),
            (
                CratesLatestResolver(name="package", package="datadog-opentelemetry"),
                {"crate": {"max_stable_version": "0.1.0", "max_version": "0.2.0"}},
                ModuleVersion(name="package", module="datadog-opentelemetry", version="0.1.0"),
            ),
        ],
    )
    def test_package_registry_resolvers_return_versions(
        self,
        monkeypatch: pytest.MonkeyPatch,
        resolver: NpmLatestResolver | PypiLatestResolver | RubygemsLatestResolver | CratesLatestResolver,
        payload: dict[str, Any],
        expected: ModuleVersion,
    ) -> None:
        calls = _stub_get_json(monkeypatch, lambda _url, _headers: payload)

        resolved = resolver.resolve({})

        assert resolved == expected
        assert len(calls) == 1

    def test_crates_latest_resolver_falls_back_to_max_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_get_json(
            monkeypatch,
            lambda _url, _headers: {
                "crate": {
                    "max_stable_version": None,
                    "max_version": "0.2.0",
                },
            },
        )
        resolver = CratesLatestResolver(name="package", package="datadog-opentelemetry")

        resolved = resolver.resolve({})

        assert resolved == ModuleVersion(name="package", module="datadog-opentelemetry", version="0.2.0")

    def test_crates_latest_resolver_sends_descriptive_user_agent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _stub_get_json(
            monkeypatch,
            lambda _url, _headers: {
                "crate": {
                    "max_stable_version": "0.1.0",
                },
            },
        )
        resolver = CratesLatestResolver(name="package", package="datadog-opentelemetry")

        resolver.resolve({})

        assert calls == [
            (
                "https://crates.io/api/v1/crates/datadog-opentelemetry",
                {
                    "Accept": "application/json",
                    "User-Agent": "system-tests-target-artifacts (https://github.com/DataDog/system-tests)",
                },
            ),
        ]

    @pytest.mark.parametrize(
        ("resolver", "payload", "match"),
        [
            (
                NpmLatestResolver(name="package", package="dd-trace"),
                {},
                "NPM package dd-trace did not include a version",
            ),
            (
                PypiLatestResolver(name="package", package="ddtrace"),
                {},
                "Expected PyPI package ddtrace info to be an object",
            ),
            (
                RubygemsLatestResolver(name="package", package="datadog"),
                {"version": ""},
                "RubyGems package datadog did not include a version",
            ),
            (
                CratesLatestResolver(name="package", package="datadog-opentelemetry"),
                {"crate": {}},
                "crate datadog-opentelemetry did not include a version",
            ),
        ],
    )
    def test_package_registry_resolvers_reject_missing_versions(
        self,
        monkeypatch: pytest.MonkeyPatch,
        resolver: NpmLatestResolver | PypiLatestResolver | RubygemsLatestResolver | CratesLatestResolver,
        payload: dict[str, Any],
        match: str,
    ) -> None:
        _stub_get_json(monkeypatch, lambda _url, _headers: payload)

        with pytest.raises(TargetArtifactError, match=match):
            resolver.resolve({})

    def test_go_module_latest_resolver_returns_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        module = "github.com/DataDog/dd-trace-go/v2"

        def fake_run(
            args: list[str],
            *,
            capture_output: bool,
            check: bool,
            text: bool,
        ) -> subprocess.CompletedProcess[str]:
            assert args == ["go", "list", "-m", "-json", f"{module}@latest"]
            assert capture_output is True
            assert check is False
            assert text is True
            return _completed_process(args, stdout='{"Version": "v1.2.3"}')

        monkeypatch.setattr("utils.target_artifacts.resolvers.subprocess.run", fake_run)
        resolver = GoModuleLatestResolver(name="module", module=module)

        resolved = resolver.resolve({})

        assert resolved == ModuleVersion(name="module", module=module, version="v1.2.3")

    @pytest.mark.parametrize(
        ("run_result", "match"),
        [
            (FileNotFoundError(), "go was not found"),
            (_completed_process([], returncode=1, stderr="module not found"), "module not found"),
            (_completed_process([], stdout="{not-json"), "Unable to parse Go module metadata"),
            (
                _completed_process([], stdout='{"Path": "github.com/DataDog/dd-trace-go/v2"}'),
                "did not include a version",
            ),
        ],
    )
    def test_go_module_latest_resolver_wraps_go_failures(
        self,
        monkeypatch: pytest.MonkeyPatch,
        run_result: subprocess.CompletedProcess[str] | FileNotFoundError,
        match: str,
    ) -> None:
        def fake_run(
            args: list[str],
            *,
            capture_output: bool,
            check: bool,
            text: bool,
        ) -> subprocess.CompletedProcess[str]:
            assert capture_output is True
            assert check is False
            assert text is True
            if isinstance(run_result, FileNotFoundError):
                raise run_result
            return _completed_process(
                args, returncode=run_result.returncode, stdout=run_result.stdout, stderr=run_result.stderr
            )

        monkeypatch.setattr("utils.target_artifacts.resolvers.subprocess.run", fake_run)
        resolver = GoModuleLatestResolver(name="module", module="github.com/DataDog/dd-trace-go/v2")

        with pytest.raises(TargetArtifactError, match=match):
            resolver.resolve({})


@scenarios.test_the_test
class Test_TargetArtifactExternalContracts:
    def test_public_github_branch_contract(self) -> None:
        resolved = GitHubBranchResolver(
            name="library_branch",
            repository="DataDog/dd-trace-py",
            default_value="main",
        ).resolve({})

        assert resolved.branch == "main"
        assert resolved.repository == "DataDog/dd-trace-py"
        assert len(resolved.sha) == 40
        assert all(character in "0123456789abcdef" for character in resolved.sha)

    def test_public_github_latest_release_contract_includes_assets(self) -> None:
        resolved = GitHubLatestReleaseResolver(
            name="release",
            repository="DataDog/datadog-lambda-python",
            include_assets=True,
        ).resolve({})

        assert resolved.repository == "DataDog/datadog-lambda-python"
        assert resolved.tag_name.startswith("v")
        assert resolved.assets
        assert all(asset.name for asset in resolved.assets)
        assert all(
            asset.browser_download_url.startswith(
                "https://github.com/DataDog/datadog-lambda-python/releases/download/",
            )
            for asset in resolved.assets
        )

    def test_public_github_actions_artifact_contract_uses_unauthenticated_request(self) -> None:
        resolved = GitHubActionsArtifactResolver(
            name="workflow_artifact",
            repository="DataDog/httpd-datadog",
            workflow="dev.yml",
            artifact_name="mod_datadog_artifact",
            default_value="main",
        ).resolve({})

        assert resolved.repository == "DataDog/httpd-datadog"
        assert resolved.workflow == "dev.yml"
        assert resolved.branch == "main"
        assert len(resolved.commit_sha) == 40
        assert all(character in "0123456789abcdef" for character in resolved.commit_sha)
        assert resolved.run_url.startswith("https://github.com/DataDog/httpd-datadog/actions/runs/")
        assert "mod_datadog_artifact" in resolved.artifact_name
        assert resolved.archive_download_url.startswith(
            "https://api.github.com/repos/DataDog/httpd-datadog/actions/artifacts/",
        )

    @pytest.mark.parametrize(
        "resolver",
        [
            NpmLatestResolver(name="package", package="dd-trace"),
            PypiLatestResolver(name="package", package="ddtrace"),
            RubygemsLatestResolver(name="package", package="datadog"),
            CratesLatestResolver(name="package", package="datadog-opentelemetry"),
        ],
    )
    def test_public_package_registry_contracts_return_versions(
        self,
        resolver: NpmLatestResolver | PypiLatestResolver | RubygemsLatestResolver | CratesLatestResolver,
    ) -> None:
        resolved = resolver.resolve({})

        assert resolved.module
        assert resolved.version
        assert any(character.isdigit() for character in resolved.version)


@scenarios.test_the_test
class Test_TargetArtifactModules:
    @pytest.mark.parametrize("target", sorted(COMPONENT_GROUPS.all))
    @pytest.mark.parametrize("environment", ["dev", "prod"])
    def test_every_target_has_real_staging_behavior(self, target: str, environment: str) -> None:
        target_environment = load_target_environment(Path.cwd(), target, environment)
        env = {}
        if environment == "dev":
            env = {
                "AUTO_INJECT_TARGET_BRANCH": "auto-inject-branch",
                "LIBRARY_TARGET_BRANCH": "library-branch",
                "ORCHESTRION_TARGET_BRANCH": "orchestrion-branch",
            }
        resolver = FakeResolver()
        resolved = {
            artifact_resolver.name: resolver.resolve(artifact_resolver, env)
            for artifact_resolver in target_environment.artifact_inputs(env)
        }

        entries = target_environment.artifact_entries(resolved)

        assert entries, f"{target} {environment} did not emit artifact entries"
        assert all(entry.content.endswith("\n") for entry in entries)
        assert all("placeholder" not in entry.content.lower() for entry in entries)
        if environment == "prod":
            assert all(":latest" not in entry.content for entry in entries)
            assert all("@latest" not in entry.content for entry in entries)

    def test_c_dev_supports_independent_branch_overrides(self) -> None:
        target_environment = load_target_environment(Path.cwd(), "c", "dev")
        env = {
            "AUTO_INJECT_TARGET_BRANCH": "auto-inject-branch",
            "LIBRARY_TARGET_BRANCH": "library-branch",
        }
        resolver = FakeResolver()
        resolved = {
            artifact_resolver.name: resolver.resolve(artifact_resolver, env)
            for artifact_resolver in target_environment.artifact_inputs(env)
        }

        entries = {entry.filename: entry.content.strip() for entry in target_environment.artifact_entries(resolved)}

        assert entries == {
            "c-injector-image": f"installtesting.datad0g.com/apm-inject-package:{SHA}",
            "c-library-image": f"installtesting.datad0g.com/apm-library-c-package:{SHA}",
        }

    def test_workflow_artifact_entries_are_credential_free_json(self) -> None:
        target_environment = load_target_environment(Path.cwd(), "python_lambda", "dev")
        env: dict[str, str] = {}
        resolver = FakeResolver()
        resolved = {
            artifact_resolver.name: resolver.resolve(artifact_resolver, env)
            for artifact_resolver in target_environment.artifact_inputs(env)
        }

        entry = target_environment.artifact_entries(resolved)[0]
        payload = json.loads(entry.content)

        assert entry.filename.endswith(".json")
        assert payload["commit_sha"] == SHA
        assert "token" not in entry.content.lower()

    def test_provider_package_selectors_have_build_consumers(self) -> None:
        build_script = Path("utils/build/build.sh").read_text(encoding="utf-8")

        assert "binaries/dotnet-package-image" in build_script
        assert "datadog-dotnet-apm*.tar.gz" in build_script
        assert "binaries/php-package-image" in build_script
        assert "dd-library-php-*-linux-gnu.tar.gz" in build_script
        assert "datadog-setup.php" in build_script

    def test_staged_java_otel_selector_has_installer_consumer(self) -> None:
        target_environment = load_target_environment(Path.cwd(), "java_otel", "dev")
        env = {"LIBRARY_TARGET_BRANCH": "ignored"}
        resolver = FakeResolver()
        resolved = {
            artifact_resolver.name: resolver.resolve(artifact_resolver, env)
            for artifact_resolver in target_environment.artifact_inputs(env)
        }

        entries = target_environment.artifact_entries(resolved)
        installer = Path("utils/build/docker/java_otel/install_opentelemetry.sh").read_text(encoding="utf-8")

        assert {entry.filename for entry in entries} == {"java-otel-load-from-release"}
        assert "java-otel-load-from-release" in installer

    def test_lambda_workflow_metadata_is_parsed_with_jq(self) -> None:
        for installer_path, metadata_filename in (
            (
                Path("utils/build/docker/python_lambda/install_datadog_lambda.sh"),
                "python-lambda-github-actions-artifact.json",
            ),
            (
                Path("utils/build/docker/nodejs_lambda/install_datadog_lambda.sh"),
                "nodejs-lambda-github-actions-artifact.json",
            ),
        ):
            installer = installer_path.read_text(encoding="utf-8")

            assert metadata_filename in installer
            assert "jq -r '.archive_download_url'" in installer
