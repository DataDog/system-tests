from __future__ import annotations

from dataclasses import dataclass

from utils._context.component_version import Version
from .const import LIBRARIES


@dataclass
class Context:
    library: str
    library_version: Version
    variant: str

    @staticmethod
    def create(library: str, library_version_string: str, variant: str) -> Context | None:
        if (
            library not in LIBRARIES
            or not library_version_string
            or not (library_version := Version(library_version_string))
        ):
            return None
        return Context(library, library_version, variant)

    def __hash__(self):
        return hash((self.library, str(self.library_version), self.variant))
