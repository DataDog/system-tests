from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class TargetArtifactError(Exception):
    """Expected target artifact configuration or resolution failure."""


@dataclass(frozen=True)
class ArtifactEntry:
    filename: str
    content: str


@dataclass(frozen=True)
class LiteralValue:
    name: str
    value: str


@dataclass(frozen=True)
class BranchReference:
    name: str
    repository: str
    branch: str
    sha: str


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    browser_download_url: str


@dataclass(frozen=True)
class GitHubReleaseReference:
    name: str
    repository: str
    tag_name: str
    assets: tuple[ReleaseAsset, ...] = ()


@dataclass(frozen=True)
class GitHubActionsArtifactReference:
    name: str
    repository: str
    workflow: str
    branch: str
    commit_sha: str
    run_id: int
    run_url: str
    artifact_id: int
    artifact_name: str
    archive_download_url: str


@dataclass(frozen=True)
class OciImageReference:
    name: str
    image: str
    digest: str
    reference: str


@dataclass(frozen=True)
class ModuleVersion:
    name: str
    module: str
    version: str


type ResolvedArtifactInput = (
    LiteralValue
    | BranchReference
    | GitHubReleaseReference
    | GitHubActionsArtifactReference
    | OciImageReference
    | ModuleVersion
)


class ArtifactResolver(Protocol):
    """Resolver implementations document their resolved model type in their class docstring."""

    @property
    def name(self) -> str:
        """Resolved input name."""
        ...

    def resolve(self, env: dict[str, str], /) -> ResolvedArtifactInput:
        """Resolve one declared artifact input."""
        ...


@runtime_checkable
class TargetArtifactEnvironment(Protocol):
    def artifact_inputs(
        self,
        env: dict[str, str],
    ) -> tuple[ArtifactResolver, ...]:
        """Declare the inputs needed to produce artifact entries."""
        ...

    def artifact_entries(
        self,
        resolved_inputs: dict[str, ResolvedArtifactInput],
    ) -> tuple[ArtifactEntry, ...]:
        """Return text artifact entries from resolved inputs."""
        ...
