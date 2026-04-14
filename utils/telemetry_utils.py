from utils._context.component_version import ComponentVersion


class TelemetryUtils:
    test_loaded_dependencies = {
        "dotnet": {"NodaTime": False},
        "nodejs": {"glob": False},
        "java": {"org.apache.httpcomponents:httpclient": False},
        "ruby": {"bundler": False},
        "python": {"requests": False},
        "golang": {"github.com/tinylib/msgp": False},
        "php": {"weblog/acme": False},
    }

    @staticmethod
    def get_loaded_dependency(library: str) -> dict[str, bool]:
        return TelemetryUtils.test_loaded_dependencies[library]

    @staticmethod
    def get_dd_appsec_sca_enabled_names(library: ComponentVersion) -> list[str]:
        if library == "php":
            return ["appsec.sca_enabled"]
        return ["DD_APPSEC_SCA_ENABLED"]
