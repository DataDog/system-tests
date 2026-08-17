from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    BranchReference,
    ModuleVersion,
)
from utils.target_artifacts.resolvers import GitHubBranchResolver, PypiLatestResolver


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubBranchResolver]:
        return (
            GitHubBranchResolver(
                name="library_branch",
                repository="DataDog/dd-trace-py",
                variable_name="LIBRARY_TARGET_BRANCH",
                default_value="main",
            ),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, BranchReference],
    ) -> tuple[ArtifactEntry]:
        return (text_entry("python-load-from-s3", resolved_inputs["library_branch"].sha),)


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[PypiLatestResolver]:
        return (PypiLatestResolver(name="ddtrace", package="ddtrace"),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, ModuleVersion],
    ) -> tuple[ArtifactEntry]:
        version = resolved_inputs["ddtrace"].version
        return (text_entry("python-load-from-pip", f"ddtrace=={version}"),)
