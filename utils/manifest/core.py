from typing import Any
from utils.manifest.parser import load
from utils._context.component_version import Version
from utils.manifest.rule import get_rules, match_rule
from utils.manifest.types import ManifestData
from utils.manifest.validate import validate_manifest_files as validate
import utils.manifest._const as const


class Manifest:
    def __init__(
        self,
        library: str,
        library_version: Version | None = None,
        weblog: str | None = None,
        agent_version: Version | None = None,
        dd_apm_inject_version: Version | None = None,
        k8s_cluster_agent_version: Version | None = None,
        path: str = const.default_manifests_path,
    ):
        data = load(path)
        self.rules = get_rules(
            data, library, library_version, weblog, agent_version, dd_apm_inject_version, k8s_cluster_agent_version
        )

    @staticmethod
    def parse(path: str = const.default_manifests_path) -> ManifestData:
        return load(path)

    @staticmethod
    def validate(path: str = const.default_manifests_path) -> None:
        validate(path)

    def get_declarations(self, nodeid: str) -> list[tuple[Any, str | None]]:
        ret: list[tuple[Any, str | None]] = []
        for rule, declarations in self.rules.items():
            if not match_rule(rule, nodeid):
                continue
            ret += declarations
        return ret
