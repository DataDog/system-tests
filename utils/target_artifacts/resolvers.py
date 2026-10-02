from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

from .models import (
    BranchReference,
    GitHubActionsArtifactReference,
    GitHubReleaseReference,
    LiteralValue,
    ModuleVersion,
    OciImageReference,
    ReleaseAsset,
    TargetArtifactError,
)

REQUEST_TIMEOUT_SECONDS = 30
FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
CRATES_IO_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "system-tests-target-artifacts (https://github.com/DataDog/system-tests)",
}


@dataclass(frozen=True)
class EnvResolver:
    """Resolve an environment variable to LiteralValue."""

    name: str
    variable_name: str = ""
    default_value: str = ""

    def resolve(self, env: dict[str, str]) -> LiteralValue:
        value = env.get(self.variable_name, self.default_value)
        return LiteralValue(name=self.name, value=value)


class _GitHubResolver:
    @staticmethod
    def _github_headers(env: dict[str, str]) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github.v3+json"}
        token = env.get("GITHUB_TOKEN", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _github_get(self, url: str, env: dict[str, str]) -> dict[str, Any]:
        return _get_json(url, self._github_headers(env))


@dataclass(frozen=True)
class GitHubBranchResolver(_GitHubResolver):
    """Resolve a GitHub branch or commit SHA to BranchReference."""

    name: str
    repository: str
    variable_name: str = ""
    default_value: str = ""

    def resolve(self, env: dict[str, str]) -> BranchReference:
        branch = env.get(self.variable_name, self.default_value)
        if not branch:
            raise TargetArtifactError(f"Missing branch for input '{self.name}'")
        if FULL_SHA_PATTERN.match(branch):
            return BranchReference(
                name=self.name,
                repository=self.repository,
                branch=branch,
                sha=branch,
            )

        payload = self._github_get(
            f"https://api.github.com/repos/{self.repository}/branches/{quote(branch, safe='')}",
            env,
        )
        commit = _mapping(payload.get("commit"), f"branch '{branch}' commit")
        sha = commit.get("sha")
        if not isinstance(sha, str) or FULL_SHA_PATTERN.match(sha) is None:
            raise TargetArtifactError(f"Branch '{branch}' in {self.repository} did not resolve to a commit SHA")
        return BranchReference(
            name=self.name,
            repository=self.repository,
            branch=branch,
            sha=sha,
        )


@dataclass(frozen=True)
class GitHubLatestReleaseResolver(_GitHubResolver):
    """Resolve the latest GitHub release to GitHubReleaseReference."""

    name: str
    repository: str
    include_assets: bool = False

    def resolve(self, env: dict[str, str]) -> GitHubReleaseReference:
        payload = self._github_get(f"https://api.github.com/repos/{self.repository}/releases/latest", env)
        tag_name = payload.get("tag_name")
        if not isinstance(tag_name, str) or not tag_name:
            raise TargetArtifactError(f"Latest release for {self.repository} did not include a tag")

        assets: tuple[ReleaseAsset, ...] = ()
        if self.include_assets:
            raw_assets = payload.get("assets")
            if not isinstance(raw_assets, list):
                raise TargetArtifactError(f"Latest release for {self.repository} did not include assets")
            assets = tuple(_release_asset(asset) for asset in raw_assets)

        return GitHubReleaseReference(
            name=self.name,
            repository=self.repository,
            tag_name=tag_name,
            assets=assets,
        )


@dataclass(frozen=True)
class GitHubActionsArtifactResolver(_GitHubResolver):
    """Resolve a GitHub Actions workflow artifact to GitHubActionsArtifactReference."""

    name: str
    repository: str
    workflow: str
    artifact_name: str
    variable_name: str = ""
    default_value: str = ""
    ignore_failed_workflow: bool = True

    def resolve(self, env: dict[str, str]) -> GitHubActionsArtifactReference:
        branch = env.get(self.variable_name, self.default_value)
        if not branch:
            raise TargetArtifactError(f"Missing workflow branch for input '{self.name}'")

        runs_payload = self._github_get(
            "https://api.github.com/repos/"
            f"{self.repository}/actions/workflows/{self.workflow}/runs"
            f"?branch={quote(branch, safe='')}&status=completed&per_page=100",
            env,
        )
        runs = runs_payload.get("workflow_runs")
        if not isinstance(runs, list):
            raise TargetArtifactError(f"Workflow runs were not returned for {self.repository}")

        selected_run: dict[str, Any] | None = None
        for run in runs:
            run_mapping = _mapping(run, "workflow run")
            if self.ignore_failed_workflow and run_mapping.get("conclusion") == "failure":
                continue
            selected_run = run_mapping
            break

        if selected_run is None:
            raise TargetArtifactError(f"No completed workflow run found for {self.repository}@{branch}")

        artifacts_url = selected_run.get("artifacts_url")
        if not isinstance(artifacts_url, str):
            raise TargetArtifactError("Selected workflow run did not include artifacts_url")
        artifacts_payload = self._github_get(f"{artifacts_url}?per_page=100", env)
        artifacts = artifacts_payload.get("artifacts")
        if not isinstance(artifacts, list):
            raise TargetArtifactError("Workflow artifacts were not returned")

        selected_artifact: dict[str, Any] | None = None
        for artifact in artifacts:
            artifact_mapping = _mapping(artifact, "workflow artifact")
            artifact_name = artifact_mapping.get("name")
            if isinstance(artifact_name, str) and self.artifact_name in artifact_name:
                selected_artifact = artifact_mapping
                break

        if selected_artifact is None:
            raise TargetArtifactError(f"No artifact containing '{self.artifact_name}' found for {self.repository}")

        return GitHubActionsArtifactReference(
            name=self.name,
            repository=self.repository,
            workflow=self.workflow,
            branch=branch,
            commit_sha=_required_str(selected_run, "head_sha"),
            run_id=_required_int(selected_run, "id"),
            run_url=_required_str(selected_run, "html_url"),
            artifact_id=_required_int(selected_artifact, "id"),
            artifact_name=_required_str(selected_artifact, "name"),
            archive_download_url=_required_str(selected_artifact, "archive_download_url"),
        )


@dataclass(frozen=True)
class OciDigestResolver:
    """Resolve an OCI image tag to OciImageReference."""

    name: str
    image: str = ""
    variable_name: str = ""
    default_value: str = ""

    def resolve(self, env: dict[str, str]) -> OciImageReference:
        image = env.get(self.variable_name, self.image or self.default_value)
        if not image:
            raise TargetArtifactError(f"Missing OCI image for input '{self.name}'")
        if "@sha256:" in image:
            digest = image.rsplit("@", 1)[1]
            return OciImageReference(
                name=self.name,
                image=image,
                digest=digest,
                reference=image,
            )

        try:
            result = subprocess.run(
                ["docker", "buildx", "imagetools", "inspect", image],
                capture_output=True,
                check=False,
                text=True,
            )
        except FileNotFoundError as exc:
            raise TargetArtifactError("Unable to resolve OCI digest: docker was not found") from exc
        if result.returncode != 0:
            raise TargetArtifactError(f"Unable to resolve OCI digest for {image}: {result.stderr.strip()}")

        digest = ""
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("Digest:"):
                digest = stripped.removeprefix("Digest:").strip()
                break

        if not digest.startswith("sha256:"):
            raise TargetArtifactError(f"Unable to find OCI digest for {image}")

        last_slash = image.rfind("/")
        last_colon = image.rfind(":")
        repository = image[:last_colon] if last_colon > last_slash else image
        return OciImageReference(
            name=self.name,
            image=image,
            digest=digest,
            reference=f"{repository}@{digest}",
        )


@dataclass(frozen=True)
class NpmLatestResolver:
    """Resolve the latest npm package version to ModuleVersion."""

    name: str
    package: str

    def resolve(self, _env: dict[str, str]) -> ModuleVersion:
        payload = _get_json(f"https://registry.npmjs.org/{quote(self.package, safe='@/')}/latest", {})
        version = payload.get("version")
        if not isinstance(version, str) or not version:
            raise TargetArtifactError(f"NPM package {self.package} did not include a version")
        return ModuleVersion(name=self.name, module=self.package, version=version)


@dataclass(frozen=True)
class PypiLatestResolver:
    """Resolve the latest PyPI package version to ModuleVersion."""

    name: str
    package: str

    def resolve(self, _env: dict[str, str]) -> ModuleVersion:
        payload = _get_json(f"https://pypi.org/pypi/{quote(self.package, safe='')}/json", {})
        info = _mapping(payload.get("info"), f"PyPI package {self.package} info")
        version = info.get("version")
        if not isinstance(version, str) or not version:
            raise TargetArtifactError(f"PyPI package {self.package} did not include a version")
        return ModuleVersion(name=self.name, module=self.package, version=version)


@dataclass(frozen=True)
class RubygemsLatestResolver:
    """Resolve the latest RubyGems package version to ModuleVersion."""

    name: str
    package: str

    def resolve(self, _env: dict[str, str]) -> ModuleVersion:
        payload = _get_json(f"https://rubygems.org/api/v1/gems/{quote(self.package, safe='')}.json", {})
        version = payload.get("version")
        if not isinstance(version, str) or not version:
            raise TargetArtifactError(f"RubyGems package {self.package} did not include a version")
        return ModuleVersion(name=self.name, module=self.package, version=version)


@dataclass(frozen=True)
class CratesLatestResolver:
    """Resolve the latest crates.io package version to ModuleVersion."""

    name: str
    package: str

    def resolve(self, _env: dict[str, str]) -> ModuleVersion:
        payload = _get_json(f"https://crates.io/api/v1/crates/{quote(self.package, safe='')}", CRATES_IO_HEADERS)
        crate = _mapping(payload.get("crate"), f"crate {self.package}")
        version = crate.get("max_stable_version") or crate.get("max_version")
        if not isinstance(version, str) or not version:
            raise TargetArtifactError(f"crate {self.package} did not include a version")
        return ModuleVersion(name=self.name, module=self.package, version=version)


@dataclass(frozen=True)
class GoModuleLatestResolver:
    """Resolve the latest Go module version to ModuleVersion."""

    name: str
    module: str

    def resolve(self, _env: dict[str, str]) -> ModuleVersion:
        try:
            result = subprocess.run(
                ["go", "list", "-m", "-json", f"{self.module}@latest"],
                capture_output=True,
                check=False,
                text=True,
            )
        except FileNotFoundError as exc:
            raise TargetArtifactError("Unable to resolve Go module: go was not found") from exc
        if result.returncode != 0:
            raise TargetArtifactError(f"Unable to resolve Go module {self.module}: {result.stderr.strip()}")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise TargetArtifactError(f"Unable to parse Go module metadata for {self.module}") from exc
        version = payload.get("Version")
        if not isinstance(version, str) or not version:
            raise TargetArtifactError(f"Go module {self.module} did not include a version")
        return ModuleVersion(name=self.name, module=self.module, version=version)


def _get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    try:
        response = requests.get(url, headers=dict(headers), timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise TargetArtifactError(f"Unable to resolve artifact metadata from {url}: {exc}") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise TargetArtifactError(f"Unable to parse artifact metadata from {url}") from exc
    return _mapping(payload, f"response from {url}")


def _mapping(value: object, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TargetArtifactError(f"Expected {description} to be an object")
    return value


def _release_asset(value: object) -> ReleaseAsset:
    item = _mapping(value, "release asset")
    return ReleaseAsset(
        name=_required_str(item, "name"),
        browser_download_url=_required_str(item, "browser_download_url"),
    )


def _required_str(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise TargetArtifactError(f"Expected '{key}' to be a non-empty string")
    return result


def _required_int(value: dict[str, Any], key: str) -> int:
    result = value.get(key)
    if not isinstance(result, int):
        raise TargetArtifactError(f"Expected '{key}' to be an integer")
    return result
