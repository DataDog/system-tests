from utils import weblog, interfaces, scenarios, features, context
from utils._decorators import missing_feature
from utils.interfaces._library.miscs import validate_process_tags


@scenarios.tracing_config_nondefault
@features.process_tags
@missing_feature(
    condition=context.library.name != "java" or context.weblog_variant == "spring-boot-3-native",
    reason="Not yet implemented",
)
class Test_Process_Tags:
    """Test the presence of process tags in various payloads."""

    def setup_tracing_process_tags(self):
        self.req = weblog.get("/status?code=200")

    def test_tracing_process_tags(self):
        # Get all the spans from the agent
        found = False
        for data, _ in interfaces.agent.get_spans(self.req):
            # Check that the agent managed to extract the process tags from the first chunk
            for payload in data["request"]["content"]["tracerPayloads"]:
                process_tags = payload["tags"]["_dd.tags.process"]
                validate_process_tags(process_tags)
                found = True
        assert found, "Process tags are missing"

    def setup_remote_config_process_tags(self):
        self.req = weblog.get("/status?code=200")

    def test_remote_config_process_tags(self):
        found = False
        for data in interfaces.library.get_data(path_filters="/v0.7/config"):
            process_tags_list = data["request"]["content"]["client"]["client_tracer"]["process_tags"]
            assert isinstance(process_tags_list, list)
            validate_process_tags(",".join(process_tags_list))
            found = True
        assert found, "Process tags are missing"

    def setup_telemetry_process_tags(self):
        self.req = weblog.get("/status?code=200")

    def test_telemetry_process_tags(self):
        found = False
        telemetry_data = list(interfaces.library.get_telemetry_data())
        for data in telemetry_data:
            validate_process_tags(data["request"]["content"]["application"]["process_tags"])
            found = True
        assert found, "Process tags are missing"
