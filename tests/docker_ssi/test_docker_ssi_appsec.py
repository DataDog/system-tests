from urllib.parse import urlparse

from utils import scenarios, interfaces, weblog, features, missing_feature, context


@features.appsec_service_activation_origin_metric
@scenarios.docker_ssi_appsec
class TestDockerSSIAppsecFeatures:
    """Test the ssi in a simulated host injection environment (docker container + test agent)
    We test that the injection is performed and appsec is enabled and telemetry is generated.
    """

    def setup_telemetry_source_ssi(self):
        parsed_url = urlparse(scenarios.docker_ssi.weblog_url)
        self.r = weblog.request("GET", parsed_url.path, domain=parsed_url.hostname, port=parsed_url.port)

    @missing_feature(condition=context.library in ("nodejs", "java"), reason="No implemented")
    def test_telemetry_source_ssi(self):
        root_span = interfaces.test_agent.get_traces(request=self.r)
        assert root_span, f"No traces found for request {self.r.get_rid()}"
        assert "service" in root_span, f"No service name found in root_span: {root_span}"
        # Get all captured telemetry configuration data
        configurations = interfaces.test_agent.get_telemetry_configurations(
            root_span["service"], root_span["meta"]["runtime-id"]
        )

        # Check that instrumentation source is ssi
        injection_source = configurations.get("DD_APPSEC_ENABLED")
        assert injection_source, f"instrumentation_source not found in configuration {configurations}"
        assert injection_source["value"]["value"] in [
            "1",
            1,
            True,
        ], f"instrumentation_source value is not ssi {injection_source}"
        assert injection_source["origin"] == "ssi", f"instrumentation_source value is not ssi {injection_source}"
