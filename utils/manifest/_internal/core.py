from pathlib import Path
from .parser import load
from utils._context.component_version import Version
from .rule import get_rules, match_rule
from .types import ManifestData, SkipDeclaration
from .validate import validate_manifest_files as validate
from .const import default_manifests_path


class Manifest:
    """Provides a simple way to get information from the manifests"""

    def __init__(
        self,
        library: str | None = None,
        library_version: Version | None = None,
        weblog: str | None = None,
        agent_version: Version | None = None,
        dd_apm_inject_version: Version | None = None,
        k8s_cluster_agent_version: Version | None = None,
        path: Path = default_manifests_path,
    ):
        """Parses all the manifest files on creation and filters the results based on
        the information provided
        """
        self.data = load(path)
        self.rules = None
        if library:
            self.update_rules(
                library, library_version, weblog, agent_version, dd_apm_inject_version, k8s_cluster_agent_version
            )

    def update_rules(
        self,
        library: str,
        library_version: Version | None = None,
        weblog: str | None = None,
        agent_version: Version | None = None,
        dd_apm_inject_version: Version | None = None,
        k8s_cluster_agent_version: Version | None = None,
    ):
        self.rules, self.condition_tracker = get_rules(
            self.data, library, library_version, weblog, agent_version, dd_apm_inject_version, k8s_cluster_agent_version
        )

    @staticmethod
    def parse(path: Path = default_manifests_path) -> ManifestData:
        """Returns a manifest containing the parsed data from all manifests files in path

        Args:
            path (str): Path to the manifest directory. Defaults to 'manifests/'

        """
        return load(path)

    @staticmethod
    def validate(path: Path = default_manifests_path) -> None:
        """Runs a series of checks on the manifest files including:
        - nodeids exist
        - manifests are sorted
        - manifests can be parsed without errors

        Args:
            path (str, optional): Path to the manifest directory. Defaults to 'manifests/'

        """
        validate(path)

    def get_declarations(
        self, nodeid: str, declaration_sources: list[tuple[str, list[tuple[int, int]]]] | None = None
    ) -> list[SkipDeclaration]:
        """Returns a dict containing all the SkipDeclarations that should be applied
        to the nodeid provided

        Args:
            nodeid (str): The nodeid for which to get the SkipDeclarations
            declaration_sources (dict[str, list[int]]): is modified to add the rule
                and condition index that declarations are originating from

        """
        ret: list[SkipDeclaration] = []
        assert type(self.rules) is not dict[str, list[SkipDeclaration]], (
            "You need to provide a library name to the constructor or call update_rules"
        )
        for rule, declarations in self.rules.items():
            if not match_rule(rule, nodeid):
                continue
            ret += declarations
            if declaration_sources is not None:
                declaration_sources.append((rule, self.condition_tracker[rule]))
        return ret
