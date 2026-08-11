from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    ModuleVersion,
)
from utils.target_artifacts.resolvers import PypiLatestResolver

PACKAGE_NAME = "opentelemetry-distro"


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[PypiLatestResolver]:
        return (PypiLatestResolver(name="otel_package", package=PACKAGE_NAME),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, ModuleVersion],
    ) -> tuple[ArtifactEntry]:
        version = resolved_inputs["otel_package"].version
        return (text_entry("python-otel-load-from-pip", f"{PACKAGE_NAME}[otlp]=={version}"),)


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[PypiLatestResolver]:
        return (PypiLatestResolver(name="otel_package", package=PACKAGE_NAME),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, ModuleVersion],
    ) -> tuple[ArtifactEntry]:
        version = resolved_inputs["otel_package"].version
        return (text_entry("python-otel-load-from-pip", f"{PACKAGE_NAME}[otlp]=={version}"),)
