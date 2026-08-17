from __future__ import annotations


from utils.target_artifacts.entry_helpers import provider_fetch_entries, text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    BranchReference,
    GitHubReleaseReference,
)
from utils.target_artifacts.resolvers import GitHubBranchResolver, GitHubLatestReleaseResolver


def _normalize_branch_for_image_tag(branch_name: str) -> str:
    return branch_name.replace("/", "_")


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubBranchResolver]:
        return (
            GitHubBranchResolver(
                name="library_branch",
                repository="DataDog/dd-trace-dotnet",
                variable_name="LIBRARY_TARGET_BRANCH",
                default_value="master",
            ),
        )

    def artifact_entries(self, resolved_inputs: dict[str, BranchReference]) -> tuple[ArtifactEntry, ArtifactEntry]:
        resolved_branch = resolved_inputs["library_branch"]
        fetch_selector = (
            f"ghcr.io/datadog/dd-trace-dotnet/dd-trace-dotnet:{_normalize_branch_for_image_tag(resolved_branch.branch)}"
        )
        return provider_fetch_entries(
            fetch_filename="dotnet-package-image",
            fetch_selector=fetch_selector,
            marker_filename="dotnet-package-selection",
            bounded_selector=resolved_branch.sha,
        )


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubLatestReleaseResolver]:
        return (GitHubLatestReleaseResolver(name="release", repository="DataDog/dd-trace-dotnet"),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, GitHubReleaseReference],
    ) -> tuple[ArtifactEntry]:
        return (text_entry("dotnet-load-from-release", resolved_inputs["release"].tag_name),)
