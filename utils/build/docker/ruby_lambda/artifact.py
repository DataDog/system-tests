from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    BranchReference,
    GitHubReleaseReference,
)
from utils.target_artifacts.resolvers import GitHubBranchResolver, GitHubLatestReleaseResolver


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubBranchResolver]:
        return (
            GitHubBranchResolver(
                name="library_branch",
                repository="DataDog/datadog-lambda-rb",
                variable_name="LIBRARY_TARGET_BRANCH",
                default_value="main",
            ),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, BranchReference],
    ) -> tuple[ArtifactEntry]:
        return (
            text_entry(
                "ruby-lambda-load-from-git",
                f"https://github.com/DataDog/datadog-lambda-rb@{resolved_inputs['library_branch'].sha}",
            ),
        )


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubLatestReleaseResolver]:
        return (GitHubLatestReleaseResolver(name="release", repository="DataDog/datadog-lambda-rb"),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, GitHubReleaseReference],
    ) -> tuple[ArtifactEntry]:
        return (text_entry("ruby-lambda-load-from-release", resolved_inputs["release"].tag_name),)
