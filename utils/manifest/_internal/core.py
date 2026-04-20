from pathlib import Path
import re

from utils._context.component_version import Version

from .parser import load
from .rule import get_rules, match_rule
from .types import ManifestData, SkipDeclaration
from .validate import validate_manifest_files as validate
from .const import default_manifests_path
from .format import yml_sort


class Manifest:
    """Provides a simple way to get information from the manifests"""

    data: ManifestData
    rules: dict[str, list[SkipDeclaration]] | None
    condition_tracker: dict[str, list[tuple[int, int]]]

    def __init__(
        self,
        components: dict[str, Version] | None = None,
        weblog: str | None = None,
        path: Path = default_manifests_path,
    ):
        """Parses all the manifest files on creation and filters the results based on
        the information provided
        """
        self.data = load(path)
        self.rules = None
        self._components = components
        if components is not None:
            self.update_rules(components, weblog)

    def update_rules(
        self,
        components: dict[str, Version],
        weblog: str | None = None,
    ):
        self.rules, self.condition_tracker = get_rules(self.data, components, weblog)

    @staticmethod
    def parse(path: Path = default_manifests_path) -> ManifestData:
        """Returns a manifest containing the parsed data from all manifests files in path

        Args:
            path (str): Path to the manifest directory. Defaults to 'manifests/'

        """
        return load(path)

    @staticmethod
    def validate(path: Path = default_manifests_path, *, assume_sorted: bool = False) -> None:
        """Runs a series of checks on the manifest files including:
        - nodeids exist
        - manifests are sorted
        - manifests can be parsed without errors

        Args:
            path (str, optional): Path to the manifest directory. Defaults to 'manifests/'
            assume_sorted (bool) : Weather to assume that the manifests are already sorted.

        """
        validate(path, assume_sorted=assume_sorted)

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
        assert self.rules is not None, "You need to provide a library name to the constructor or call update_rules"
        for rule, declarations in self.rules.items():
            if not match_rule(rule, nodeid):
                continue
            ret += declarations
            if declaration_sources is not None:
                declaration_sources.append((rule, self.condition_tracker[rule]))
        return ret

    @staticmethod
    def format(path: Path = default_manifests_path) -> None:
        """Formats the manifest files:
        - sorts the nodeids

        Args:
            path (str, optional): Path to the manifest directory. Defaults to 'manifests/'

        """
        yml_sort(path)


_LOWER_BOUND_RE = re.compile(r"(?:>=?|\^)(\d+\.\d+(?:\.\d+)?[.\w+-]*)")


def assert_versions_not_ahead_of_current(
    manifest_data: ManifestData,
    components: dict[str, Version],
) -> list[str]:
    """Check that no manifest condition declares a version higher than the current component version.

    In dev mode, any version boundary declared in the manifest must not exceed the version currently being tested.
    Both component_version and excluded_component_version fields are checked. Prerelease versions of the current
    version are not treated as equivalent to the release: 5.2.0-dev is strictly below 5.2.0.
    """
    errors = []

    for nodeid, conditions in manifest_data.items():
        for condition in conditions:
            component = condition["component"]
            if component not in components:
                continue

            current_version = components[component]

            semver_ranges = (
                condition.get("component_version"),
                condition.get("excluded_component_version"),
            )

            for sem_range in semver_ranges:
                if sem_range is None:
                    continue

                for match in _LOWER_BOUND_RE.finditer(sem_range.expression):
                    try:
                        declared = Version(match.group(1))
                    except (ValueError, TypeError):
                        continue

                    if declared > current_version:
                        errors.append(
                            f"{nodeid} [{component}]: declared version {declared}"
                            f" exceeds current version {current_version}"
                        )

    return errors
