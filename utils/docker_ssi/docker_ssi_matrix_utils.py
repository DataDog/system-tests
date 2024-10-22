from utils.docker_ssi.docker_ssi_definitions import JavaRuntimeInstallableVersions, PythonRuntimeInstallableVersions


def resolve_runtime_version(library, runtime):
    """ For installable runtimes, get the version identifier. ie JAVA_11 """
    if library == "java":
        return JavaRuntimeInstallableVersions.get_version_id(runtime)
    elif library == "python":
        return PythonRuntimeInstallableVersions.get_version_id(runtime)

    raise ValueError(f"Library {library} not supported")
