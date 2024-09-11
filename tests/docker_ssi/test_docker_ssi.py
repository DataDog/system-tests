from utils import scenarios, features, context, irrelevant, bug
from utils.tools import logger
from utils import scenarios, features, interfaces
from utils.docker_ssi.docker_ssi_matrix_utils import check_if_version_supported
import time
from utils import weblog
from urllib.parse import urlparse
from utils.tools import logger, get_rid_from_request


@scenarios.docker_ssi
class TestDockerSSIFeatures:
    """ Test the ssi in a simulated host injection environment (docker container + test agent) 
    We test that the injection is performed and traces and telemetry are generated. 
    If the language version is not supported, we only check that we don't break the app and telemetry is generated."""

    def _setup_all(self):
        parsed_url = urlparse(context.scenario.weblog_url)
        self.r = weblog.request("GET", parsed_url.path, domain=parsed_url.hostname, port=parsed_url.port)
        logger.info(f"Setup Docker SSI installation {self.r}")
        time.sleep(5)  # Wait for 5 seconds to allow the test agent to send traces

    def setup_install(self):
        self._setup_all()

    @features.ssi_guardrails
    @bug(
        condition="centos-7" in context.scenario.weblog_variant and context.scenario.library.library == "java",
        reason="There is a issue building the image on centos 7",
    )
    def test_install(self):
        logger.info(f"Testing Docker SSI installation: {context.scenario.library.library}")
        assert self.r.status_code == 200, f"Failed to get response from {context.scenario.weblog_url}"
        supported_lang_runtime = check_if_version_supported(
            context.scenario.library, context.scenario.installed_runtime
        )
        if supported_lang_runtime:
            # If the language version is supported there are traces related with the request
            traces_for_request = interfaces.test_agent.get_traces(request=self.r)
            assert traces_for_request, f"No traces found for request {get_rid_from_request(self.r)}"
            assert "runtime-id" in traces_for_request["meta"], "No runtime-id found in traces"

            # There is telemetry data related with the runtime-id
            telemetry_data = interfaces.test_agent.get_telemetry_for_runtime(traces_for_request["meta"]["runtime-id"])
            assert telemetry_data, "No telemetry data found"

        # There is telemetry data about the auto instrumentation. We only validate there is data
        telemetry_autoinject_data = interfaces.test_agent.get_telemetry_for_autoinject()
        assert len(telemetry_autoinject_data) >= 1
        for data in telemetry_autoinject_data:
            assert data["metric"] == "inject.success"

    def setup_service_name(self):
        self._setup_all()

    @features.ssi_service_naming
    @irrelevant(condition=not context.scenario.weblog_variant.startswith("tomcat-app"))
    def test_service_name(self):
        logger.info("Testing Docker SSI service name")
        # There are traces related with the request and the service name is payment-service
        traces_for_request = interfaces.test_agent.get_traces(request=self.r)
        assert traces_for_request, f"No traces found for request {get_rid_from_request(self.r)}"
        assert "service" in traces_for_request, "No service name found in traces"
        assert (
            traces_for_request["service"] == "payment-service"
        ), f"Service name is not payment-service but {traces_for_request['service']}"
