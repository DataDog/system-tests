from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageConfiguration:
    artifact_environment_variable: str
    artifact_runfile: str
    duration_manifest: str
    library: str
    version: str
    version_environment_variable: str


_LANGUAGE_CONFIGURATIONS = {
    "golang": LanguageConfiguration(
        artifact_environment_variable="SYSTEM_TESTS_GO_PARAMETRIC_SERVER",
        artifact_runfile="utils/build/docker/golang/parametric/go_parametric_server_/go_parametric_server",
        duration_manifest="go_test_durations.json",
        library="golang",
        version="v2.4.0",
        version_environment_variable="SYSTEM_TESTS_GO_LIBRARY_VERSION",
    ),
    "python": LanguageConfiguration(
        artifact_environment_variable="SYSTEM_TESTS_PYTHON_PARAMETRIC_ARCHIVE",
        artifact_runfile="bazel/parametric/python_server_archive.zip",
        duration_manifest="python_test_durations.json",
        library="python",
        version="4.13.1",
        version_environment_variable="SYSTEM_TESTS_PYTHON_LIBRARY_VERSION",
    ),
}


def language_configuration(language: str) -> LanguageConfiguration:
    try:
        return _LANGUAGE_CONFIGURATIONS[language]
    except KeyError as error:
        supported = ", ".join(sorted(_LANGUAGE_CONFIGURATIONS))
        raise ValueError(f"Unknown Bazel parametric language {language!r}; expected one of: {supported}") from error
