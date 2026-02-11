from __future__ import annotations

from dataclasses import dataclass

from utils._context.component_version import Version
from .const import LIBRARIES


def strip_java_build_metadata(library: str, version_string: str) -> str:
    """Strip build metadata (commit SHA after +) from Java versions."""
    if library == "java" and "+" in version_string:
        return version_string.split("+")[0]
    return version_string


@dataclass
class Context:
    library: str
    library_version: Version
    variant: str
    processors = [strip_java_build_metadata]

    @staticmethod
    def create(library: str, library_version_string: str, variant: str) -> Context | None:
        if library not in LIBRARIES or not library_version_string:
            return None
        for processor in Context.processors:
            library_version_string = processor(library, library_version_string)
        if not (library_version := Version(library_version_string)):
            return None
        return Context(library, library_version, variant)

    def __hash__(self):
        return hash((self.library, str(self.library_version), self.variant))
