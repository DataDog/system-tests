from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    BranchReference,
    ModuleVersion,
)
from utils.target_artifacts.resolvers import CratesLatestResolver, GitHubBranchResolver


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubBranchResolver]:
        return (
            GitHubBranchResolver(
                name="library_branch",
                repository="DataDog/dd-trace-rs",
                variable_name="LIBRARY_TARGET_BRANCH",
                default_value="main",
            ),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, BranchReference],
    ) -> tuple[ArtifactEntry]:
        return (text_entry("rust-load-from-git", resolved_inputs["library_branch"].sha),)


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[CratesLatestResolver]:
        return (
            CratesLatestResolver(
                name="datadog_opentelemetry",
                package="datadog-opentelemetry",
            ),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, ModuleVersion],
    ) -> tuple[ArtifactEntry]:
        version = resolved_inputs["datadog_opentelemetry"].version
        return (text_entry("rust-load-from-crates", version),)
