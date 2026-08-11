from __future__ import annotations

import re

from utils.target_artifacts.entry_helpers import provider_fetch_entries, text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    BranchReference,
    GitHubReleaseReference,
)
from utils.target_artifacts.resolvers import GitHubBranchResolver, GitHubLatestReleaseResolver


def _normalize_branch_for_image_tag(branch_name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", branch_name.lower())
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:63].rstrip("-")


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubBranchResolver]:
        return (
            GitHubBranchResolver(
                name="library_branch",
                repository="DataDog/dd-trace-php",
                variable_name="LIBRARY_TARGET_BRANCH",
                default_value="master",
            ),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, BranchReference],
    ) -> tuple[ArtifactEntry, ArtifactEntry]:
        resolved_branch = resolved_inputs["library_branch"]
        fetch_selector = (
            f"ghcr.io/datadog/dd-trace-php/dd-library-php:{_normalize_branch_for_image_tag(resolved_branch.branch)}"
        )
        return provider_fetch_entries(
            fetch_filename="php-package-image",
            fetch_selector=fetch_selector,
            marker_filename="php-package-selection",
            bounded_selector=resolved_branch.sha,
        )


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubLatestReleaseResolver]:
        return (GitHubLatestReleaseResolver(name="release", repository="DataDog/dd-trace-php"),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, GitHubReleaseReference],
    ) -> tuple[ArtifactEntry]:
        return (text_entry("php-load-from-release", resolved_inputs["release"].tag_name),)
