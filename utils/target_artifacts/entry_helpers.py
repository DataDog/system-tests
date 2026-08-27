from __future__ import annotations

import json

from .models import (
    ArtifactEntry,
    GitHubActionsArtifactReference,
    TargetArtifactError,
)


def text_entry(filename: str, content: str) -> ArtifactEntry:
    return ArtifactEntry(filename=filename, content=f"{content.rstrip()}\n")


def json_entry(filename: str, payload: dict[str, object]) -> ArtifactEntry:
    if not filename.endswith(".json"):
        raise TargetArtifactError(f"JSON artifact entry '{filename}' must use a .json extension")
    return ArtifactEntry(filename=filename, content=f"{json.dumps(payload, sort_keys=True)}\n")


def gha_artifact_entry(filename: str, artifact: GitHubActionsArtifactReference) -> ArtifactEntry:
    """Create a JSON artifact entry from a GitHub Actions artifact reference."""
    return json_entry(
        filename,
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
    )


def provider_fetch_entries(
    *,
    fetch_filename: str,
    fetch_selector: str,
    marker_filename: str,
    bounded_selector: str,
) -> tuple[ArtifactEntry, ArtifactEntry]:
    """Create a provider fetch entry plus its bounded selection marker.

    Some providers require installer-facing fetch selectors that are not
    themselves bounded, such as branch-derived package image tags. The fetch
    entry is consumed by the build to retrieve the provider artifact, while the
    marker entry records the bounded selector used for cache identity.
    """
    return (
        text_entry(fetch_filename, fetch_selector),
        text_entry(marker_filename, bounded_selector),
    )
