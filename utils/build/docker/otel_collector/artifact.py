from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    OciImageReference,
)
from utils.target_artifacts.resolvers import OciDigestResolver

DEFAULT_IMAGE = "otel/opentelemetry-collector-contrib:0.137.0"


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[OciDigestResolver]:
        return (
            OciDigestResolver(
                name="collector_image",
                image=DEFAULT_IMAGE,
                variable_name="OTEL_COLLECTOR_IMAGE",
            ),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, OciImageReference],
    ) -> tuple[ArtifactEntry]:
        return (text_entry("otel_collector-image", resolved_inputs["collector_image"].reference),)


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[OciDigestResolver]:
        return (OciDigestResolver(name="collector_image", image=DEFAULT_IMAGE),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, OciImageReference],
    ) -> tuple[ArtifactEntry]:
        return (text_entry("otel_collector-image", resolved_inputs["collector_image"].reference),)
