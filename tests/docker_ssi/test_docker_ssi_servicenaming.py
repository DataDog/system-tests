from urllib.parse import urlparse

from utils import (
    scenarios,
    features,
    interfaces,
)
from utils import weblog, logger


@features.ssi_service_naming
@scenarios.docker_ssi_servicenaming
class TestDockerServiceNaming:
    """Test the ssi in a simulated host injection environment (docker container + test agent)
    We test the auto service naming geration feature.
    """

    _r = None

    def setup_service_name(self):
        if TestDockerServiceNaming._r is None:
            parsed_url = urlparse(scenarios.docker_ssi_servicenaming.weblog_url)
            logger.info(
                f"Setting up Docker SSI installation WEBLOG_URL {scenarios.docker_ssi_servicenaming.weblog_url}"
            )
            TestDockerServiceNaming._r = weblog.request(
                "GET", parsed_url.path, domain=parsed_url.hostname, port=parsed_url.port
            )
            logger.info(f"Setup Docker SSI installation {TestDockerServiceNaming._r}")

        self.r = TestDockerServiceNaming._r

    def test_service_name(self):
        logger.info("Testing Docker SSI service name")
        # There are traces related with the request and the service name is payment-service
        traces_for_request = interfaces.test_agent.get_traces(request=self.r)
        assert traces_for_request, f"No traces found for request {self.r.get_rid()}"
        assert "service" in traces_for_request, "No service name found in traces"
        assert traces_for_request["service"] == "payment-service", (
            f"Service name is not payment-service but {traces_for_request['service']}"
        )
