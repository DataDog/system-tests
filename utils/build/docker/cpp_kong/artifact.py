from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    BranchReference,
    GitHubReleaseReference,
)
from utils.target_artifacts.resolvers import GitHubBranchResolver, GitHubLatestReleaseResolver


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubBranchResolver, GitHubBranchResolver]:
        return (
            GitHubBranchResolver(
                name="cpp_branch",
                repository="DataDog/dd-trace-cpp",
                variable_name="DD_TRACE_CPP_TARGET_BRANCH",
                default_value="main",
            ),
            GitHubBranchResolver(
                name="plugin_branch",
                repository="DataDog/kong-plugin-ddtrace",
                variable_name="LIBRARY_TARGET_BRANCH",
                default_value="main",
            ),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, BranchReference],
    ) -> tuple[ArtifactEntry, ArtifactEntry]:
        return (
            text_entry(
                "cpp-load-from-git",
                f"https://github.com/DataDog/dd-trace-cpp@{resolved_inputs['cpp_branch'].sha}",
            ),
            text_entry(
                "cpp-kong-plugin-git",
                f"https://github.com/DataDog/kong-plugin-ddtrace@{resolved_inputs['plugin_branch'].sha}",
            ),
        )


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubLatestReleaseResolver, GitHubLatestReleaseResolver]:
        return (
            GitHubLatestReleaseResolver(name="cpp_release", repository="DataDog/dd-trace-cpp"),
            GitHubLatestReleaseResolver(name="plugin_release", repository="DataDog/kong-plugin-ddtrace"),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, GitHubReleaseReference],
    ) -> tuple[ArtifactEntry, ArtifactEntry]:
        return (
            text_entry(
                "cpp-load-from-git",
                f"https://github.com/DataDog/dd-trace-cpp@{resolved_inputs['cpp_release'].tag_name}",
            ),
            text_entry("cpp-kong-load-from-release", resolved_inputs["plugin_release"].tag_name),
        )
