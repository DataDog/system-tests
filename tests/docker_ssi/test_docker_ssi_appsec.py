from urllib.parse import urlparse

from utils import scenarios, interfaces, weblog, logger


@scenarios.docker_ssi_appsec
class TestDockerSSIAppsecFeatures:
    """Test the ssi in a simulated host injection environment (docker container + test agent)
    We test that the injection is performed and appsec is enabled and telemetry is generated.
    """

    def setup_telemetry_appsec(self):
        parsed_url = urlparse(scenarios.docker_ssi.weblog_url)
        self.r = weblog.request("GET", parsed_url.path, domain=parsed_url.hostname, port=parsed_url.port)

    def test_telemetry_appsec(self):
        # TODO Create a method on interfaces.test_agent to get the telemetry data for appsec
        telemetry_autoinject_data = interfaces.test_agent.get_telemetry_for_autoinject()
        assert len(telemetry_autoinject_data) >= 1
        for data in telemetry_autoinject_data:
            logger.info(f"Telemetry data: {data}")
