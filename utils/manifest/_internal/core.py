from pathlib import Path
from .parser import load
from utils._context.component_version import Version
from .rule import get_rules, match_rule
from .types import ManifestData, SkipDeclaration
from .validate import validate_manifest_files as validate
from .const import default_manifests_path
from .format import yml_sort


class Manifest:
    """Provides a simple way to get information from the manifests"""

    def __init__(
        self,
        components: dict[str, Version],
        weblog: str,
        path: Path = default_manifests_path,
    ):
        """Parses all the manifest files on creation and filters the results based on
        the information provided
        """
        data = load(path)
        self.rules = get_rules(data, components, weblog)

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

    def get_declarations(self, nodeid: str) -> list[SkipDeclaration]:
        """Returns a dict containing all the SkipDeclarations that should be applied
        to the nodeid provided

        Args:
            nodeid (str): The nodeid for which to get the SkipDeclarations

        """
        ret: list[SkipDeclaration] = []
        for rule, declarations in self.rules.items():
            if not match_rule(rule, nodeid):
                continue
            ret += declarations
        return ret

    @staticmethod
    def format(path: Path = default_manifests_path) -> None:
        """Formats the manifest files:
        - sorts the nodeids

        Args:
            path (str, optional): Path to the manifest directory. Defaults to 'manifests/'

        """
        yml_sort(path)
