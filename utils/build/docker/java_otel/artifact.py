from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    GitHubReleaseReference,
)
from utils.target_artifacts.resolvers import GitHubLatestReleaseResolver

REPOSITORY = "open-telemetry/opentelemetry-java-instrumentation"


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubLatestReleaseResolver]:
        return (GitHubLatestReleaseResolver(name="release", repository=REPOSITORY),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, GitHubReleaseReference],
    ) -> tuple[ArtifactEntry]:
        return (text_entry("java-otel-load-from-release", resolved_inputs["release"].tag_name),)


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[GitHubLatestReleaseResolver]:
        return (GitHubLatestReleaseResolver(name="release", repository=REPOSITORY),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, GitHubReleaseReference],
    ) -> tuple[ArtifactEntry]:
        return (text_entry("java-otel-load-from-release", resolved_inputs["release"].tag_name),)
