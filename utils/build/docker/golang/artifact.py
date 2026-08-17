from __future__ import annotations

from typing import cast

from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    BranchReference,
    ModuleVersion,
    OciImageReference,
)
from utils.target_artifacts.resolvers import GitHubBranchResolver, GoModuleLatestResolver, OciDigestResolver

type ArtifactInputResolver = GitHubBranchResolver | GoModuleLatestResolver | OciDigestResolver
type ResolvedGoInput = BranchReference | ModuleVersion | OciImageReference

GO_MODULES = (
    "github.com/DataDog/dd-trace-go/v2",
    "github.com/DataDog/dd-trace-go/contrib/database/sql/v2",
    "github.com/DataDog/dd-trace-go/contrib/net/http/v2",
    "github.com/DataDog/dd-trace-go/contrib/google.golang.org/grpc/v2",
    "github.com/DataDog/dd-trace-go/contrib/99designs/gqlgen/v2",
    "github.com/DataDog/dd-trace-go/contrib/gin-gonic/gin/v2",
    "github.com/DataDog/dd-trace-go/contrib/graphql-go/graphql/v2",
    "github.com/DataDog/dd-trace-go/contrib/graph-gophers/graphql-go/v2",
    "github.com/DataDog/dd-trace-go/contrib/go-chi/chi.v5/v2",
    "github.com/DataDog/dd-trace-go/contrib/IBM/sarama/v2",
    "github.com/DataDog/dd-trace-go/contrib/labstack/echo.v4/v2",
    "github.com/DataDog/dd-trace-go/contrib/sirupsen/logrus/v2",
)

DEV_SERVICE_EXTENSIONS_IMAGE = "ghcr.io/datadog/dd-trace-go/service-extensions-callout:dev"
DEV_HAPROXY_SPOA_IMAGE = "ghcr.io/datadog/dd-trace-go/haproxy-spoa:dev"
PROD_SERVICE_EXTENSIONS_IMAGE = "ghcr.io/datadog/dd-trace-go/service-extensions-callout:latest"
PROD_HAPROXY_SPOA_IMAGE = "ghcr.io/datadog/dd-trace-go/haproxy-spoa:latest"


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[ArtifactInputResolver, ...]:
        inputs: list[ArtifactInputResolver] = [
            GitHubBranchResolver(
                name="library_branch",
                repository="DataDog/dd-trace-go",
                variable_name="LIBRARY_TARGET_BRANCH",
                default_value="main",
            ),
            OciDigestResolver(name="service_extensions_image", image=DEV_SERVICE_EXTENSIONS_IMAGE),
            OciDigestResolver(name="haproxy_spoa_image", image=DEV_HAPROXY_SPOA_IMAGE),
        ]
        if env.get("ORCHESTRION_TARGET_BRANCH"):
            inputs.append(
                GitHubBranchResolver(
                    name="orchestrion_branch",
                    repository="DataDog/orchestrion",
                    variable_name="ORCHESTRION_TARGET_BRANCH",
                )
            )
        else:
            inputs.append(GoModuleLatestResolver(name="orchestrion_version", module="github.com/DataDog/orchestrion"))
        return tuple(inputs)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, ResolvedGoInput],
    ) -> tuple[ArtifactEntry, ArtifactEntry, ArtifactEntry, ArtifactEntry]:
        library_branch = cast(BranchReference, resolved_inputs["library_branch"])
        sha = library_branch.sha
        return _entries_for_go_ref(resolved_inputs, sha)


class Prod:
    def artifact_inputs(
        self,
        env: dict[str, str],
    ) -> tuple[GoModuleLatestResolver, GoModuleLatestResolver, OciDigestResolver, OciDigestResolver]:
        return (
            GoModuleLatestResolver(name="library_version", module="github.com/DataDog/dd-trace-go/v2"),
            GoModuleLatestResolver(name="orchestrion_version", module="github.com/DataDog/orchestrion"),
            OciDigestResolver(name="service_extensions_image", image=PROD_SERVICE_EXTENSIONS_IMAGE),
            OciDigestResolver(name="haproxy_spoa_image", image=PROD_HAPROXY_SPOA_IMAGE),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, ResolvedGoInput],
    ) -> tuple[ArtifactEntry, ArtifactEntry, ArtifactEntry, ArtifactEntry]:
        library_version = cast(ModuleVersion, resolved_inputs["library_version"])
        version = library_version.version
        return _entries_for_go_ref(resolved_inputs, version)


def _entries_for_go_ref(
    resolved_inputs: dict[str, ResolvedGoInput],
    go_ref: str,
) -> tuple[ArtifactEntry, ArtifactEntry, ArtifactEntry, ArtifactEntry]:
    if "orchestrion_branch" in resolved_inputs:
        orchestrion_branch = cast(BranchReference, resolved_inputs["orchestrion_branch"])
        orchestrion_ref = orchestrion_branch.sha
    else:
        orchestrion_version = cast(ModuleVersion, resolved_inputs["orchestrion_version"])
        orchestrion_ref = orchestrion_version.version

    service_extensions_image = cast(OciImageReference, resolved_inputs["service_extensions_image"])
    haproxy_spoa_image = cast(OciImageReference, resolved_inputs["haproxy_spoa_image"])

    return (
        text_entry("golang-load-from-go-get", "\n".join(f"{module}@{go_ref}" for module in GO_MODULES)),
        text_entry("orchestrion-load-from-go-get", f"github.com/DataDog/orchestrion@{orchestrion_ref}"),
        text_entry(
            "golang-service-extensions-callout-image",
            service_extensions_image.reference,
        ),
        text_entry("golang-haproxy-spoa-image", haproxy_spoa_image.reference),
    )
