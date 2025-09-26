from urllib.parse import urlparse

from utils import (
    irrelevant,
    missing_feature,
    scenarios,
    features,
    context,
    interfaces,
)
from utils import weblog, logger


@scenarios.docker_ssi_crashtracking
class TestDockerSSICrash:
    """Test the ssi in a simulated host injection environment (docker container + test agent)
    We test scenarios when the application crashes and sends a crash report.
    """

    _r = None

    def setup_crash(self):
        if TestDockerSSICrash._r is None:
            parsed_url = urlparse(scenarios.docker_ssi_crashtracking.weblog_url)
            logger.info(
                f"Setting up Docker SSI installation WEBLOG_URL {scenarios.docker_ssi_crashtracking.weblog_url}"
            )
            r_ready = weblog.request("GET", parsed_url.path, domain=parsed_url.hostname, port=parsed_url.port)
            logger.info(f"Check Docker SSI installation https status: {r_ready.status_code}")
            parsed_url = urlparse(scenarios.docker_ssi_crashtracking.weblog_url + "/crashme")
            TestDockerSSICrash._r = weblog.request(
                "GET", parsed_url.path, domain=parsed_url.hostname, port=parsed_url.port
            )
            logger.info(f"Setup Docker SSI installation {TestDockerSSICrash._r}")

        self.r = TestDockerSSICrash._r

    @features.ssi_crashtracking
    @missing_feature(
        condition=context.library in ("java", "php", "ruby"), reason="No implemented the endpoint /crashme"
    )
    @irrelevant(context.library == "python" and context.installed_language_runtime < "3.7.0")
    @irrelevant(context.library == "nodejs" and context.installed_language_runtime < "17.0")
    def test_crash(self):
        """Validate that a crash report is generated when the application crashes"""
        logger.info(f"Testing Docker SSI crash tracking: {context.library.name}")
        assert (
            self.r.status_code is None
        ), f"Response from request {scenarios.docker_ssi_crashtracking.weblog_url + '/crashme'} was supposed to fail: {self.r}"

        # No traces should have been generated
        assert not interfaces.test_agent.get_traces(
            self.r
        ), f"Traces found for request {scenarios.docker_ssi_crashtracking.weblog_url + '/crashme'}"

        # Crash report should have been generated
        crash_reports = interfaces.test_agent.get_crash_reports()
        assert crash_reports, "No crash report found"
        assert len(crash_reports) == 1, "More than one crash report found"
