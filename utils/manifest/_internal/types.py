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


class Condition(TypedDict):
    component: str
    component_version: NotRequired[SemverRange]
    excluded_component_version: NotRequired[SemverRange]
    weblog: NotRequired[str | list[str]]
    excluded_weblog: NotRequired[str | list[str]]
    declaration: SkipDeclaration


class ManifestData(dict[str, list[Condition]]):
    pass
