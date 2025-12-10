from utils._decorators import CustomSpec as SemverRange
from typing import NotRequired, TypedDict
from dataclasses import dataclass
from utils._decorators import _TestDeclaration


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
