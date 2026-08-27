from __future__ import annotations


from utils.target_artifacts.entry_helpers import gha_artifact_entry, text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    GitHubActionsArtifactReference,
    GitHubReleaseReference,
)
from utils.target_artifacts.resolvers import GitHubActionsArtifactResolver, GitHubLatestReleaseResolver


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubActionsArtifactResolver]:
        return (
            GitHubActionsArtifactResolver(
                name="workflow_artifact",
                repository="DataDog/datadog-lambda-js",
                workflow="build_layer.yml",
                artifact_name="datadog_lambda_node18.12",
                variable_name="LIBRARY_TARGET_BRANCH",
                default_value="main",
                ignore_failed_workflow=False,
            ),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, GitHubActionsArtifactReference],
    ) -> tuple[ArtifactEntry]:
        return (gha_artifact_entry("nodejs-lambda-github-actions-artifact.json", resolved_inputs["workflow_artifact"]),)


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubLatestReleaseResolver]:
        return (GitHubLatestReleaseResolver(name="release", repository="DataDog/datadog-lambda-js"),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, GitHubReleaseReference],
    ) -> tuple[ArtifactEntry]:
        return (text_entry("nodejs-lambda-load-from-release", resolved_inputs["release"].tag_name),)
