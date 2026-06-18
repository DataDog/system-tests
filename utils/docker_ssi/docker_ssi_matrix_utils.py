from typing import Protocol

from utils.docker_ssi.docker_ssi_definitions import (
    JavaRuntimeInstallableVersions,
    JSRuntimeInstallableVersions,
    PHPRuntimeInstallableVersions,
    PythonRuntimeInstallableVersions,
    DotnetRuntimeInstallableVersions,
    RubyRuntimeInstallableVersions,
)


class _InstallableVersions(Protocol):
    @staticmethod
    def get_version_id(version: str) -> str: ...


def resolve_runtime_version(library: str, runtime: str) -> str:
    """For installable runtimes, get the version identifier. ie JAVA_11"""
    installable_versions: dict[str, type[_InstallableVersions]] = {
        "java": JavaRuntimeInstallableVersions,
        "php": PHPRuntimeInstallableVersions,
        "python": PythonRuntimeInstallableVersions,
        "nodejs": JSRuntimeInstallableVersions,
        "dotnet": DotnetRuntimeInstallableVersions,
        "ruby": RubyRuntimeInstallableVersions,
    }
    if library not in installable_versions:
        raise ValueError(f"Library {library} not supported")

    return installable_versions[library].get_version_id(runtime)
