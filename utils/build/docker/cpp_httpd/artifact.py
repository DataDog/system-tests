from __future__ import annotations


from utils.target_artifacts.entry_helpers import json_entry, text_entry
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
                repository="DataDog/httpd-datadog",
                workflow="dev.yml",
                artifact_name="mod_datadog_artifact",
                variable_name="LIBRARY_TARGET_BRANCH",
                default_value="main",
            ),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, GitHubActionsArtifactReference],
    ) -> tuple[ArtifactEntry]:
        artifact = resolved_inputs["workflow_artifact"]
        return (
            json_entry(
                "cpp-httpd-github-actions-artifact.json",
                {
                    "archive_download_url": artifact.archive_download_url,
                    "artifact_id": artifact.artifact_id,
                    "artifact_name": artifact.artifact_name,
                    "commit_sha": artifact.commit_sha,
                    "repository": artifact.repository,
                    "run_id": artifact.run_id,
                    "run_url": artifact.run_url,
                    "workflow": artifact.workflow,
                },
            ),
        )


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubLatestReleaseResolver]:
        return (GitHubLatestReleaseResolver(name="release", repository="DataDog/httpd-datadog"),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, GitHubReleaseReference],
    ) -> tuple[ArtifactEntry]:
        return (text_entry("cpp-httpd-load-from-release", resolved_inputs["release"].tag_name),)
