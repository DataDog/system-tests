from utils._decorators import CustomSpec as SemverRange
from typing import NotRequired, TypedDict
from dataclasses import dataclass
from utils._decorators import _TestDeclaration


@dataclass
class SkipDeclaration:
    value: _TestDeclaration
    details: str | None = None

    def __init__(self, value: str, details: str | None = None):
        self.value = _TestDeclaration(value)
        self.details = details

    def __eq__(self, value: object, /) -> bool:
        assert isinstance(
            value, SkipDeclaration
        ), f"Comparison between 'SkipDeclaration and {type(value)} is not supported"
        return self.value == value.value and self.details == value.details

    def __str__(self) -> str:
        return f"{self.value} ({self.details})"

    def __hash__(self) -> int:
        return hash(str(self))


class Condition(TypedDict):
    component: str
    component_version: NotRequired[SemverRange]
    excluded_component_version: NotRequired[SemverRange]
    weblog: NotRequired[str | list[str]]
    excluded_weblog: NotRequired[str | list[str]]
    declaration: SkipDeclaration


class ManifestData(dict[str, list[Condition]]):
    pass
