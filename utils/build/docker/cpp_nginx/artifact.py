from __future__ import annotations

from typing import cast

from utils.target_artifacts.entry_helpers import json_entry, text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    GitHubActionsArtifactReference,
    GitHubReleaseReference,
)
from utils.target_artifacts.resolvers import GitHubActionsArtifactResolver, GitHubLatestReleaseResolver

type ResolvedNginxInput = GitHubActionsArtifactReference | GitHubReleaseReference


class Dev:
    def artifact_inputs(
        self,
        env: dict[str, str],
    ) -> tuple[GitHubActionsArtifactResolver, GitHubLatestReleaseResolver]:
        return (
            GitHubActionsArtifactResolver(
                name="workflow_artifact",
                repository="DataDog/nginx-datadog",
                workflow="system-tests.yml",
                artifact_name="binaries",
                variable_name="LIBRARY_TARGET_BRANCH",
                default_value="master",
                ignore_failed_workflow=False,
            ),
            GitHubLatestReleaseResolver(name="ddprof_release", repository="DataDog/ddprof"),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, ResolvedNginxInput],
    ) -> tuple[ArtifactEntry, ArtifactEntry]:
        artifact = cast(GitHubActionsArtifactReference, resolved_inputs["workflow_artifact"])
        ddprof_release = cast(GitHubReleaseReference, resolved_inputs["ddprof_release"])
        return (
            json_entry(
                "cpp-nginx-github-actions-artifact.json",
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
            text_entry("cpp-nginx-ddprof-load-from-release", ddprof_release.tag_name),
        )


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubLatestReleaseResolver, GitHubLatestReleaseResolver]:
        return (
            GitHubLatestReleaseResolver(name="release", repository="DataDog/nginx-datadog"),
            GitHubLatestReleaseResolver(name="ddprof_release", repository="DataDog/ddprof"),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, GitHubReleaseReference],
    ) -> tuple[ArtifactEntry, ArtifactEntry]:
        return (
            text_entry("cpp-nginx-load-from-release", resolved_inputs["release"].tag_name),
            text_entry("cpp-nginx-ddprof-load-from-release", resolved_inputs["ddprof_release"].tag_name),
        )
