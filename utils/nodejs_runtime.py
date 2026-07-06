import os
import re

from utils._context.component_version import ComponentVersion, Version


NODEJS_V5_MIN_RUNTIME = Version("18.0")
NODEJS_V6_MIN_RUNTIME = Version("22.0")

_RELEASE_REF_RE = re.compile(r"^v?(?P<major>\d+)\.")
_NODEJS_AWS_V6_WEBLOGS = {
    "test-app-nodejs": "test-app-nodejs-22",
    "test-app-nodejs-container": "test-app-nodejs-container-22",
    "test-app-nodejs-esm": "test-app-nodejs-esm-22",
}


def minimum_supported_nodejs_runtime(library: ComponentVersion) -> Version:
    if library >= "nodejs@6.0.0-pre":
        return NODEJS_V6_MIN_RUNTIME

    return NODEJS_V5_MIN_RUNTIME


def is_supported_nodejs_runtime(library: ComponentVersion, runtime: Version | str | None) -> bool:
    if library != "nodejs":
        return True

    if runtime is None or str(runtime) == "":
        return False

    return Version(str(runtime)) >= minimum_supported_nodejs_runtime(library)


def is_unsupported_nodejs_runtime(library: ComponentVersion, runtime: Version | str | None) -> bool:
    return library == "nodejs" and not is_supported_nodejs_runtime(library, runtime)


def infer_minimum_nodejs_runtime_for_ci(library_version: str | None = None) -> Version | None:
    explicit_runtime = os.getenv("SYSTEM_TESTS_NODEJS_MIN_RUNTIME") or os.getenv("DD_NODEJS_RUNTIME_VERSION")
    if explicit_runtime:
        return Version(explicit_runtime)

    if library_version is None:
        library_version = os.getenv("DD_INSTALLER_LIBRARY_VERSION") or os.getenv("DD_INSTALLER_LIBRARY_VERSION_NODEJS")

    if library_version:
        try:
            return minimum_supported_nodejs_runtime(ComponentVersion("nodejs", library_version))
        except ValueError:
            pass

    refs = (
        os.getenv("CI_COMMIT_BRANCH"),
        os.getenv("CI_COMMIT_REF_NAME"),
        os.getenv("CI_MERGE_REQUEST_SOURCE_BRANCH_NAME"),
        os.getenv("CI_COMMIT_TAG"),
        os.getenv("GITHUB_REF_NAME"),
        os.getenv("GITHUB_HEAD_REF"),
    )
    for ref in refs:
        if not ref:
            continue
        ref = ref.removeprefix("refs/heads/").removeprefix("refs/tags/")
        if ref == "master":
            return NODEJS_V6_MIN_RUNTIME

        match = _RELEASE_REF_RE.match(ref)
        if not match:
            continue

        major = int(match.group("major"))
        if major >= 6:
            return NODEJS_V6_MIN_RUNTIME
        if major == 5:
            return NODEJS_V5_MIN_RUNTIME

    return None


def filter_nodejs_runtimes_for_ci(
    runtimes: list[dict[str, str]], library_version: str | None = None
) -> list[dict[str, str]]:
    minimum_runtime = infer_minimum_nodejs_runtime_for_ci(library_version)
    if minimum_runtime is None:
        return runtimes

    return [runtime for runtime in runtimes if Version(runtime["version"]) >= minimum_runtime]


def select_nodejs_aws_weblog_for_ci(weblog: str, library_version: str | None = None) -> str:
    minimum_runtime = infer_minimum_nodejs_runtime_for_ci(library_version)
    if minimum_runtime is not None and minimum_runtime >= NODEJS_V6_MIN_RUNTIME:
        return _NODEJS_AWS_V6_WEBLOGS.get(weblog, weblog)

    return weblog
