from collections.abc import Callable
from utils import weblog, interfaces, scenarios, features
from utils.interfaces._library.miscs import validate_process_tags, validate_process_tags_svc


@scenarios.tracing_config_nondefault
@features.process_tags
class Test_Process_Tags:
    """Test the presence of process tags in various payloads."""

    def setup_tracing_process_tags(self):
        self.req = weblog.get("/status?code=200")

    def setup_tracing_process_tags_svc(self):
        self.setup_tracing_process_tags()

    def check_tracing_process_tags(self, validate_process_tags_func: Callable):
        # Get all the spans from the agent
        found = False
        for data, _, _ in interfaces.agent.get_traces(self.req):
            # Check that the agent managed to extract the process tags from the first chunk
            if "idxTracerPayloads" in data["request"]["content"]:
                for payload in data["request"]["content"]["idxTracerPayloads"]:
                    process_tags = payload["attributes"]["_dd.tags.process"]
                    validate_process_tags_func(process_tags)
                    found = True
            elif "tracerPayloads" in data["request"]["content"]:
                for payload in data["request"]["content"]["tracerPayloads"]:
                    process_tags = payload["tags"]["_dd.tags.process"]
                    validate_process_tags_func(process_tags)
                    found = True
        assert found, "Process tags are missing"

    def test_tracing_process_tags_svc(self):
        self.check_tracing_process_tags(validate_process_tags_svc)

    def test_tracing_process_tags(self):
        self.check_tracing_process_tags(validate_process_tags)

    def setup_remote_config_process_tags(self):
        self.req = weblog.get("/status?code=200")

    def setup_remote_config_process_tags_svc(self):
        self.setup_remote_config_process_tags()

    def check_remote_config_process_tags(self, validate_process_tags_func: Callable):
        found = False
        for data in interfaces.library.get_data(path_filters="/v0.7/config"):
            process_tags_list = data["request"]["content"]["client"]["client_tracer"]["process_tags"]
            assert isinstance(process_tags_list, list)
            validate_process_tags_func(",".join(process_tags_list))
            found = True
        assert found, "Process tags are missing"

    def test_remote_config_process_tags_svc(self):
        self.check_remote_config_process_tags(validate_process_tags_svc)

    def test_remote_config_process_tags(self):
        self.check_remote_config_process_tags(validate_process_tags)

    def setup_telemetry_process_tags(self):
        self.req = weblog.get("/status?code=200")

    def setup_telemetry_process_tags_svc(self):
        self.setup_telemetry_process_tags()

    def check_telemetry_process_tags(self, validate_process_tags_func: Callable):
        found = False
        telemetry_data = list(interfaces.library.get_telemetry_data())
        for data in telemetry_data:
            # for python, libdatadog also send telemetry on its own not containing process_tags
            payload = data["request"]["content"].get("payload")
            if payload is not None and "series" in payload:
                if any("src_library:libdatadog" in series.get("tags", []) for series in payload["series"]):
                    continue

            validate_process_tags_func(data["request"]["content"]["application"]["process_tags"])
            found = True

        assert found, "Process tags are missing"

    def test_telemetry_process_tags_svc(self):
        self.check_telemetry_process_tags(validate_process_tags_svc)

    def test_telemetry_process_tags(self):
        self.check_telemetry_process_tags(validate_process_tags)
