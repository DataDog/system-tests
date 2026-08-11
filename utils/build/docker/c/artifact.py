from __future__ import annotations

from typing import cast

from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import (
    ArtifactEntry,
    BranchReference,
    OciImageReference,
    TargetArtifactError,
)
from utils.target_artifacts.resolvers import GitHubBranchResolver, OciDigestResolver

type ArtifactInputResolver = GitHubBranchResolver | OciDigestResolver
type ResolvedCInput = BranchReference | OciImageReference

PROD_LIBRARY_IMAGE = "install.datadoghq.com/apm-library-c-package:latest"
PROD_INJECTOR_IMAGE = "install.datadoghq.com/apm-inject-package:latest"
DEV_LIBRARY_IMAGE = "installtesting.datad0g.com/apm-library-c-package"
DEV_INJECTOR_IMAGE = "installtesting.datad0g.com/apm-inject-package"


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[ArtifactInputResolver, ...]:
        inputs: list[ArtifactInputResolver] = []
        if env.get("LIBRARY_TARGET_BRANCH"):
            inputs.append(
                GitHubBranchResolver(
                    name="library_branch",
                    repository="DataDog/dd-trace-c",
                    variable_name="LIBRARY_TARGET_BRANCH",
                )
            )
        else:
            inputs.append(OciDigestResolver(name="library_image", image=PROD_LIBRARY_IMAGE))

        if env.get("AUTO_INJECT_TARGET_BRANCH"):
            inputs.append(
                GitHubBranchResolver(
                    name="injector_branch",
                    repository="DataDog/auto_inject",
                    variable_name="AUTO_INJECT_TARGET_BRANCH",
                )
            )
        else:
            inputs.append(OciDigestResolver(name="injector_image", image=PROD_INJECTOR_IMAGE))
        return tuple(inputs)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, ResolvedCInput],
    ) -> tuple[ArtifactEntry, ArtifactEntry]:
        if "library_branch" in resolved_inputs:
            library_branch = cast(BranchReference, resolved_inputs["library_branch"])
            library_ref = f"{DEV_LIBRARY_IMAGE}:{library_branch.sha}"
        else:
            library_image = cast(OciImageReference, resolved_inputs["library_image"])
            library_ref = library_image.reference

        if "injector_branch" in resolved_inputs:
            injector_branch = cast(BranchReference, resolved_inputs["injector_branch"])
            injector_ref = f"{DEV_INJECTOR_IMAGE}:{injector_branch.sha}"
        else:
            injector_image = cast(OciImageReference, resolved_inputs["injector_image"])
            injector_ref = injector_image.reference

        return (
            text_entry("c-library-image", library_ref),
            text_entry("c-injector-image", injector_ref),
        )


class Prod:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[OciDigestResolver, OciDigestResolver]:
        if env.get("LIBRARY_TARGET_BRANCH") or env.get("AUTO_INJECT_TARGET_BRANCH"):
            raise TargetArtifactError("Target branches can only be used with the development c packages")
        return (
            OciDigestResolver(name="library_image", image=PROD_LIBRARY_IMAGE),
            OciDigestResolver(name="injector_image", image=PROD_INJECTOR_IMAGE),
        )

    def artifact_entries(
        self,
        resolved_inputs: dict[str, OciImageReference],
    ) -> tuple[ArtifactEntry, ArtifactEntry]:
        return (
            text_entry("c-library-image", resolved_inputs["library_image"].reference),
            text_entry("c-injector-image", resolved_inputs["injector_image"].reference),
        )
