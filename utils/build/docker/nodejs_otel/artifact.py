from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    ModuleVersion,
)
from utils.target_artifacts.resolvers import NpmLatestResolver

PACKAGE_NAME = "@opentelemetry/auto-instrumentations-node"


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[NpmLatestResolver]:
        return (NpmLatestResolver(name="otel_package", package=PACKAGE_NAME),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, ModuleVersion],
    ) -> tuple[ArtifactEntry]:
        version = resolved_inputs["otel_package"].version
        return (text_entry("nodejs-otel-load-from-npm", f"{PACKAGE_NAME}@{version}"),)


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[NpmLatestResolver]:
        return (NpmLatestResolver(name="otel_package", package=PACKAGE_NAME),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, ModuleVersion],
    ) -> tuple[ArtifactEntry]:
        version = resolved_inputs["otel_package"].version
        return (text_entry("nodejs-otel-load-from-npm", f"{PACKAGE_NAME}@{version}"),)
