from pathlib import Path
import re

from utils._context.component_version import Version

from .parser import ALL_MANIFEST_COMPONENTS, load
from .rule import get_rules, nodeid_elements, rule_elements
from .types import ManifestData, SkipDeclaration
from .validate import validate_manifest_files as validate
from .const import default_manifests_path
from .format import yml_sort


_RANGE_RE = re.compile(r"(?:>=?|<=?|\^)(\d+\.\d+(?:\.\d+)?[.\w+-]*)")


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
        """Parses the relevant manifest files on creation and filters the results based on
        the information provided
        """
        self._path = path
        self._rules_index: dict[tuple[str, ...], list[tuple[int, str, list[SkipDeclaration]]]] = {}
        self._rule_lengths: tuple[int, ...] = ()
        if components is not None:
            self._loaded_components: set[str] | None = set(components.keys())
            self.data = load(path, components=self._loaded_components)
            self._initial_data: ManifestData = self.data
            self.rules = None
            self._components: dict[str, Version] = components
            self.update_rules(self._components, weblog)
        else:
            self._loaded_components = None
            self.data = load(path)
            self._initial_data = self.data
            self.rules = None

    def update_rules(
        self,
        components: dict[str, Version],
        weblog: str | None = None,
    ):
        if self._loaded_components is not None and self.data is self._initial_data:
            missing = [c for c in components if c in ALL_MANIFEST_COMPONENTS and c not in self._loaded_components]
            if missing:
                self._loaded_components.update(missing)
                self.data = load(self._path, components=self._loaded_components)
                self._initial_data = self.data

        self.rules, self.condition_tracker = get_rules(self.data, components, weblog)
        self._build_rules_index()

    def _build_rules_index(self) -> None:
        index: dict[tuple[str, ...], list[tuple[int, str, list[SkipDeclaration]]]] = {}
        lengths: set[int] = set()
        if self.rules is not None:
            for order_idx, (rule, declarations) in enumerate(self.rules.items()):
                key = rule_elements(rule)
                lengths.add(len(key))
                bucket = index.get(key)
                if bucket is None:
                    index[key] = [(order_idx, rule, declarations)]
                else:
                    bucket.append((order_idx, rule, declarations))
        self._rules_index = index
        self._rule_lengths = tuple(sorted(lengths))

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
        """Returns a list containing all the SkipDeclarations that should be applied
        to the nodeid provided

        Args:
            nodeid (str): The nodeid for which to get the SkipDeclarations
            declaration_sources (list[tuple[str, list[tuple[int, int]]]]): is modified to add the rule
                and condition index that declarations are originating from

        """
        assert self.rules is not None, "You need to provide a library name to the constructor or call update_rules"
        if not self._rules_index:
            return []

        n_parts = nodeid_elements(nodeid)
        n_elements = len(n_parts)

        matches: list[tuple[int, str, list[SkipDeclaration]]] = []
        for length in self._rule_lengths:
            if length > n_elements:
                break
            bucket = self._rules_index.get(n_parts[:length])
            if bucket is not None:
                matches.extend(bucket)

        if not matches:
            return []

        if len(matches) > 1:
            matches.sort(key=lambda item: item[0])

        ret: list[SkipDeclaration] = []
        for _, rule, declarations in matches:
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

    def assert_versions_not_ahead_of_current(self) -> list[str]:
        """Check that no manifest condition declares a version higher than the current component version.

        In dev mode, any version boundary declared in the manifest must not exceed the version currently being tested.
        Both component_version and excluded_component_version fields are checked. Prerelease versions of the current
        version are not treated as equivalent to the release: 5.2.0-dev is strictly below 5.2.0.
        """
        errors = []

        for nodeid, conditions in self.data.items():
            for condition in conditions:
                component = condition["component"]
                if component not in self._components:
                    continue

                current_version = self._components[component]

                semver_ranges = (
                    condition.get("component_version"),
                    condition.get("excluded_component_version"),
                )

                for sem_range in semver_ranges:
                    if sem_range is None:
                        continue

                    for match in _RANGE_RE.finditer(sem_range.expression):
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
