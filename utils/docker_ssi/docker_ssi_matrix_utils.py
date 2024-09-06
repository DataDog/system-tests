from utils.docker_ssi.docker_ssi_definitions import JavaRuntimeVersions


def resolve_runtime_version(library, runtime):
    if library == "java":
        return JavaRuntimeVersions.get_version_id(runtime)

    raise ValueError(f"Library {library} not supported")
