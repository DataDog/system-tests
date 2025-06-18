from utils import weblog, interfaces, scenarios, features, context
from utils._decorators import missing_feature
from utils.interfaces._library.miscs import validate_process_tags


@scenarios.process_tags
@features.process_tags
@missing_feature(condition=context.library.name != "java", reason="Not yet implemented")
class Test_Process_Tags:
    """Test the presence of process tags in various payloads."""

    def setup_tracing_process_tags(self):
        self.req = weblog.get("/")

    def test_tracing_process_tags(self):
        # Only the parent span should be submitted to the backend!
        spans = interfaces.agent.get_spans_list(self.req)
        assert len(spans) == 1, "Agent did not submit the spans we want!"

        # Assert the spans sent by the agent.
        span = spans[0]

        process_tags = span["meta"]["_dd.tags.process"]
        validate_process_tags(process_tags)

    def setup_remote_config_process_tags(self):
        self.req = weblog.get("/")

    def test_remote_config_process_tags(self):
        for data in interfaces.library.get_data(path_filters="/v0.7/config"):
            process_tags_list = data["request"]["content"]["client"]["client_tracer"]["process_tags"]
            assert isinstance(process_tags_list, list)
            validate_process_tags(",".join(process_tags_list))

    def setup_telemetry_process_tags(self):
        self.req = weblog.get("/")

    @missing_feature(context.library < "java@1.50.0", reason="Not yet implemented")
    def test_telemetry_process_tags(self):
        telemetry_data = list(interfaces.library.get_telemetry_data())
        for data in telemetry_data:
            validate_process_tags(data["request"]["content"]["application"]["process_tags"])

    def setup_dsm_process_tags(self):
        self.req = weblog.get("/")

    @missing_feature(context.library < "java@1.50.0", reason="Not yet implemented")
    def test_dsm_process_tags(self):
        dsm_data = list(interfaces.agent.get_dsm_data())
        for data in dsm_data:
            process_tags_list = data["request"]["content"]["ProcessTags"]
            assert isinstance(process_tags_list, list)
            validate_process_tags(",".join(process_tags_list))
