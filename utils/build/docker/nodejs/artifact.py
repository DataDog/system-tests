from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    BranchReference,
    ModuleVersion,
)
from utils.target_artifacts.resolvers import GitHubBranchResolver, NpmLatestResolver


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubBranchResolver]:
        return (
            GitHubBranchResolver(
                name="library_branch",
                repository="DataDog/dd-trace-js",
                variable_name="LIBRARY_TARGET_BRANCH",
                default_value="master",
            ),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, BranchReference],
    ) -> tuple[ArtifactEntry]:
        sha = resolved_inputs["library_branch"].sha
        return (text_entry("nodejs-load-from-npm", f"DataDog/dd-trace-js#{sha}"),)


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[NpmLatestResolver]:
        return (NpmLatestResolver(name="dd-trace", package="dd-trace"),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, ModuleVersion],
    ) -> tuple[ArtifactEntry]:
        version = resolved_inputs["dd-trace"].version
        return (text_entry("nodejs-load-from-npm", f"dd-trace@{version}"),)
