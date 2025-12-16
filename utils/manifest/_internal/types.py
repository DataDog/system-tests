from dataclasses import dataclass
from typing import NotRequired, TypedDict, Any

import semantic_version as semver

from utils._decorators import _TestDeclaration


# semver module offers two spec engine :
# 1. SimpleSpec : not a good fit because it does not allows OR clause
# 2. NpmSpec : not a good fit because it disallow prerelease version by default (6.0.0-pre is not in ">=5.0.0")
# So we use a custom one, based on NPM spec, allowing pre-release versions
class _CustomParser(semver.NpmSpec.Parser):
    @classmethod
    def range(cls, operator: Any, target: Any) -> semver.base.Range:  # noqa: ANN401
        return semver.base.Range(operator, target, prerelease_policy=semver.base.Range.PRERELEASE_ALWAYS)


class SemverRange(semver.NpmSpec):
    Parser = _CustomParser


@dataclass
class SkipDeclaration:
    """Type for skip declarations. Unlike _TestDeclaration it also contains the details"""

    value: _TestDeclaration
    details: str | None = None

    def __init__(self, value: str, details: str | None = None):
        self.value = _TestDeclaration(value)
        self.details = details

    def __eq__(self, value: object, /) -> bool:
        assert isinstance(value, SkipDeclaration), (
            f"Comparison between 'SkipDeclaration and {type(value)} is not supported"
        )
        return self.value == value.value and self.details == value.details

    def __str__(self) -> str:
        return f"{self.value} ({self.details})"

    def __hash__(self) -> int:
        return hash(str(self))


class Condition(TypedDict):
    """Type for deactivation conditions"""

    component: str
    component_version: NotRequired[SemverRange]
    excluded_component_version: NotRequired[SemverRange]
    weblog: NotRequired[list[str]]
    excluded_weblog: NotRequired[list[str]]
    declaration: SkipDeclaration


class ManifestData(dict[str, list[Condition]]):
    """A named dict[str, list[Condition]] to store manifest data
    Mapping with raw manifest data:
    --------------------------------------------------------
    -------------------------------------------------      |
    tests/dir/file.py::Class:                       |      |
    ------------------------------------            | rule |
        - weblog: weblog1              | Condition  |      |
          component_version: <4.3.5    |            |      |
          declaration: missing_feature |            |      | ManifestData
    -------------------------------------------------      |
    tests/dir/file.py::Class::func:                 |      |
    ------------------------------------            | rule |
        - weblog: weblog1              | Condition  |      |
          component_version: <4.3.5    |            |      |
          declaration: missing_feature |            |      |
    -------------------------------------------------      |
    --------------------------------------------------------
    """
