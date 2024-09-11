from utils.docker_ssi.docker_ssi_definitions import JavaRuntimeInstallableVersions
from utils._context.library_version import LibraryVersion


def resolve_runtime_version(library, runtime):
    """ For installable runtimes, get the version identifier. ie JAVA_11 """
    if library == "java":
        return JavaRuntimeInstallableVersions.get_version_id(runtime)

    raise ValueError(f"Library {library} not supported")


def check_if_version_supported(library, version):
    if version is None:
        # If we don't know the version, we can't check if it's supported
        # By default is supported
        # Usually if we don't know the version it's because the build process failed
        return True
    """ Check if language version if supported by the ssi"""
    if library == "java":
        return LibraryVersion("1.8") > LibraryVersion(version)

    raise ValueError(f"Library {library} not supported")
