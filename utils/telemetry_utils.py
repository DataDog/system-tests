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
