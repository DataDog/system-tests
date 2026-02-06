from urllib.parse import urlparse

from tests.parametric.test_telemetry import _mapped_telemetry_name
from utils import scenarios, interfaces, weblog, features, irrelevant, context


@features.appsec_service_activation_origin_metric
@scenarios.docker_ssi_appsec
class TestDockerSSIAppsecFeatures:
    """Test the ssi in a simulated host injection environment (docker container + test agent)
    We test that the injection is performed and appsec is enabled and telemetry is generated.
    """

    def setup_telemetry_source_ssi(self):
        parsed_url = urlparse(scenarios.docker_ssi_appsec.weblog_url)
        self.r = weblog.request("GET", parsed_url.path, domain=parsed_url.hostname, port=parsed_url.port)

    @irrelevant(context.library >= "python@4.0.0.dev" and context.installed_language_runtime < "3.9.0")
    @irrelevant(context.library < "python@4.0.0.dev" and context.installed_language_runtime < "3.8.0")
    @irrelevant(context.library == "ruby" and context.installed_language_runtime < "2.6.0", reason="Ruby 2.6+ required")
    def test_telemetry_source_ssi(self):
        root_span = interfaces.test_agent.get_traces(request=self.r)
        assert root_span, f"No traces found for request {self.r.get_rid()}"
        assert "service" in root_span, f"No service name found in root_span: {root_span}"

        # Get all captured telemetry configuration data
        telemetry_names: list[str] = _mapped_telemetry_name("instrumentation_source")
        configurations = interfaces.test_agent.get_telemetry_configurations()

        for name in telemetry_names:
            if name in configurations:
                instrumentation_source: dict = configurations[name]
                assert instrumentation_source.get("value") == "ssi", f"{name}=ssi not found in {configurations}"

        # Check that instrumentation source is ssi
        injection_source = configurations.get("DD_APPSEC_ENABLED") or configurations.get("appsec.enabled")
        assert injection_source, f"instrumentation_source not found in configuration {configurations}"
        assert injection_source["value"] in ["1",1,True]
