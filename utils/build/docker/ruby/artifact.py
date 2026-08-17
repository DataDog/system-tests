from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    BranchReference,
    ModuleVersion,
)
from utils.target_artifacts.resolvers import GitHubBranchResolver, RubygemsLatestResolver


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubBranchResolver]:
        return (
            GitHubBranchResolver(
                name="library_branch",
                repository="DataDog/dd-trace-rb",
                variable_name="LIBRARY_TARGET_BRANCH",
                default_value="master",
            ),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, BranchReference],
    ) -> tuple[ArtifactEntry]:
        sha = resolved_inputs["library_branch"].sha
        return (
            text_entry(
                "ruby-load-from-bundle-add",
                "gem 'datadog', require: 'datadog/auto_instrument', "
                f"git: 'https://github.com/DataDog/dd-trace-rb.git', ref: '{sha}'",
            ),
        )


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[RubygemsLatestResolver]:
        return (RubygemsLatestResolver(name="datadog", package="datadog"),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, ModuleVersion],
    ) -> tuple[ArtifactEntry]:
        version = resolved_inputs["datadog"].version
        return (
            text_entry(
                "ruby-load-from-bundle-add",
                f"gem 'datadog', '{version}', require: 'datadog/auto_instrument'",
            ),
        )
