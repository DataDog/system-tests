class TelemetryUtils:
    test_loaded_dependencies = {
        "dotnet": {"NodaTime": False},
        "nodejs": {"glob": False},
        "java": {"org.apache.httpcomponents:httpclient": False},
        "ruby": {"bundler": False},
    }

    @staticmethod
    def get_loaded_dependency(library):
        return TelemetryUtils.test_loaded_dependencies[library]

    @staticmethod
    def get_dd_appsec_sca_enabled_str(library):
        DD_APPSEC_SCA_ENABLED = "DD_APPSEC_SCA_ENABLED"
        if library == "java":
            DD_APPSEC_SCA_ENABLED = "appsec_sca_enabled"
        elif library == "nodejs":
            DD_APPSEC_SCA_ENABLED = "appsec.sca.enabled"
        elif library in ("php", "ruby"):
            DD_APPSEC_SCA_ENABLED = "appsec.sca_enabled"
        return DD_APPSEC_SCA_ENABLED
