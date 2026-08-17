from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    BranchReference,
    GitHubReleaseReference,
)
from utils.target_artifacts.resolvers import GitHubBranchResolver, GitHubLatestReleaseResolver

REPOSITORY = "DataDog/dd-trace-cpp"
GIT_URL = "https://github.com/DataDog/dd-trace-cpp"


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubBranchResolver]:
        return (
            GitHubBranchResolver(
                name="library_branch",
                repository=REPOSITORY,
                variable_name="LIBRARY_TARGET_BRANCH",
                default_value="main",
            ),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, BranchReference],
    ) -> tuple[ArtifactEntry]:
        return (text_entry("cpp-load-from-git", f"{GIT_URL}@{resolved_inputs['library_branch'].sha}"),)


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubLatestReleaseResolver]:
        return (GitHubLatestReleaseResolver(name="release", repository=REPOSITORY),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, GitHubReleaseReference],
    ) -> tuple[ArtifactEntry]:
        return (text_entry("cpp-load-from-git", f"{GIT_URL}@{resolved_inputs['release'].tag_name}"),)
