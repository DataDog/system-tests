from utils import context, missing_feature, bug, released, weblog, scenarios


@released(python="1.7.0", dotnet="2.12.0", java="0.108.1", nodejs="3.2.0")
@bug(context.uds_mode and context.library < "nodejs@3.7.0")
@missing_feature(library="cpp")
@missing_feature(library="ruby")
@missing_feature(library="php")
@missing_feature(library="golang", reason="Implemented but not merged in master")
@missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
class Test_DpendencyEnable:
    def setup_app_dependency_loaded_not_sent_dependency_collection_disabled(self):
        weblog.get("/load_dependency")

    @missing_feature(
        context.library in ("dotnet", "nodejs", "java", "golang", "python"),
        reason="DD_TELEMETRY_DEPENDENCY_COLLECTION_ENABLED flag is not implemented yet. ",
    )
    @scenarios.telemetry_dependency_loaded_test_for_dependency_collection_disabled
    def test_app_dependency_loaded_not_sent_dependency_collection_disabled(self):
        """Test app-dependencies-loaded request should not be sent if DD_TELEMETRY_DEPENDENCY_COLLECTION_ENABLED is false"""

        def validator(data):
            if data["request"]["content"].get("request_type") == "app-dependencies-loaded":
                raise Exception("request_type app-dependencies-loaded should not be sent by this tracer")

        self.validate_library_telemetry_data(validator)
