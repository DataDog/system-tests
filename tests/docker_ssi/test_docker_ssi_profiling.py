from urllib.parse import urlparse
import requests
import time
from utils import scenarios, interfaces, weblog, features, missing_feature, irrelevant, context
from utils import logger

@features.profiling
@scenarios.docker_ssi_profiling
class TestDockerSSIAppsecFeatures:
    """Test the ssi in a simulated host injection environment (docker container + test agent)
    We test that the injection is performed and profiling is enabled and telemetry is generated.
    """

    def setup_profiling(self):
        parsed_url = urlparse(scenarios.docker_ssi_profiling.weblog_url)
        self.r = weblog.request(
                "GET", parsed_url.path, domain=parsed_url.hostname, port=parsed_url.port
            )
        logger.info(f"Setup Docker SSI profiling installation {self.r}")


    def test_profiling(self):
        agent_port = scenarios.docker_ssi_profiling.agent_port
        agent_host = scenarios.docker_ssi_profiling.agent_host
        profiling_request_found = False
        timeout = 90
        mustend = time.time() + timeout
        while time.time() < mustend:
            response = requests.get(
                f"http://{agent_host}:{agent_port}/test/session/requests",
                timeout=60,
            )
            logger.info(f"Profiling request response: {response.json()}")
            for request in response.json():
                logger.info(f"Profiling request: {request}")
                if request["url"].endswith("/profiling/v1/input"):
                    profiling_request_found = True
            time.sleep(1)
        assert profiling_request_found, "No profiling request found"

