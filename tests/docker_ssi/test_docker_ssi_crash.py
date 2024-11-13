from urllib.parse import urlparse

from utils import (
    bug,
    scenarios,
    features,
    context,
    interfaces,
)
from utils import weblog
from utils.tools import logger


@scenarios.docker_ssi
class TestDockerSSICrash:
    """Test the ssi in a simulated host injection environment (docker container + test agent)
    We test scenarios when the application crashes and sends a crash report."""

    _r = None

    def setup_crash(self):
        if TestDockerSSICrash._r is None:
            parsed_url = urlparse(context.scenario.weblog_url + "/crashme")
            logger.info(f"Setting up Docker SSI installation WEBLOG_URL {context.scenario.weblog_url}")
            TestDockerSSICrash._r = weblog.request(
                "GET", parsed_url.path, domain=parsed_url.hostname, port=parsed_url.port
            )
            logger.info(f"Setup Docker SSI installation {TestDockerSSICrash._r}")

        self.r = TestDockerSSICrash._r

    @features.ssi_crashtracking
    @bug(condition=context.library != "python", reason="INPLAT-11")
    def test_crash(self):
        """Validate that a crash report is generated when the application crashes"""
        logger.info(f"Testing Docker SSI crash tracking: {context.scenario.library.library}")
        assert (
            self.r.status_code is None
        ), f"Response from request {context.scenario.weblog_url + '/crashme'} was supposed to fail: {self.r}"

        # No traces should have been generated
        assert not interfaces.test_agent.get_traces(
            self.r
        ), f"Traces found for request {context.scenario.weblog_url + '/crashme'}"

        # Crash report should have been generated
        crash_reports = interfaces.test_agent.get_crash_reports()
        assert crash_reports, "No crash report found"
        assert len(crash_reports) == 1, "More than one crash report found"
