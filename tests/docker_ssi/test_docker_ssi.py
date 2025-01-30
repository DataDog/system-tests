from urllib.parse import urlparse

from utils import scenarios, features, context, irrelevant, bug, interfaces
from utils import weblog
from utils.tools import logger, get_rid_from_request

import docker

from utils._context.containers import (
    create_network,
    DockerSSIContainer,
    APMTestAgentContainer,
    TestedContainer,
    _get_client as get_docker_client,
)


@scenarios.docker_ssi
class TestDockerSSIFeatures:
    """Test the ssi in a simulated host injection environment (docker container + test agent)
    We test that the injection is performed and traces and telemetry are generated.
    If the language version is not supported, we only check that we don't break the app and telemetry is generated."""

    _r = None

    def _setup_all(self):
        if TestDockerSSIFeatures._r is None:
            parsed_url = urlparse(context.scenario.weblog_url)
            logger.info(f"Setting up Docker SSI installation WEBLOG_URL {context.scenario.weblog_url}")
            TestDockerSSIFeatures._r = weblog.request(
                "GET", parsed_url.path, domain=parsed_url.hostname, port=parsed_url.port
            )
            logger.info(f"Setup Docker SSI installation {TestDockerSSIFeatures._r}")

        self.r = TestDockerSSIFeatures._r

    def setup_install_supported_runtime(self):
        self._setup_all()

    @features.ssi_guardrails
    @bug(condition="centos-7" in context.weblog_variant and context.library == "java", reason="APMON-1490")
    @bug(condition=context.library == "python", reason="INPLAT-11")
    @irrelevant(context.library == "java" and context.installed_language_runtime < "1.8.0_0")
    @irrelevant(context.library == "php" and context.installed_language_runtime < "7.0")
    @irrelevant(context.library == "nodejs" and context.installed_language_runtime < "17.0")
    @irrelevant(context.weblog_variant == "js-command-line")
    def test_install_supported_runtime(self):
        logger.info(f"Testing Docker SSI installation on supported lang runtime: {context.scenario.library.library}")
        assert self.r.status_code == 200, f"Failed to get response from {context.scenario.weblog_url}"

        # If the language version is supported there are traces related with the request
        traces_for_request = interfaces.test_agent.get_traces(request=self.r)
        assert traces_for_request, f"No traces found for request {get_rid_from_request(self.r)}"
        assert "runtime-id" in traces_for_request["meta"], "No runtime-id found in traces"

        # There is telemetry data related with the runtime-id
        telemetry_data = interfaces.test_agent.get_telemetry_for_runtime(traces_for_request["meta"]["runtime-id"])
        assert telemetry_data, "No telemetry data found"

    def setup_install_weblog_running(self):
        self._setup_all()

    @features.ssi_guardrails
    @bug(
        condition="centos-7" in context.scenario.weblog_variant and context.scenario.library.library == "java",
        reason="APMON-1490",
    )
    @irrelevant(context.weblog_variant == "js-command-line")
    def test_install_weblog_running(self):
        logger.info(
            f"Testing Docker SSI installation. The weblog should be running: {context.scenario.library.library}"
        )
        assert self.r.status_code == 200, f"Failed to get response from {context.scenario.weblog_url}"

    @features.ssi_guardrails
    @bug(
        condition="centos-7" in context.scenario.weblog_variant and context.scenario.library.library == "java",
        reason="APMON-1490",
    )
    @irrelevant(context.library == "java" and context.installed_language_runtime < "1.8.0_0")
    @irrelevant(context.library == "php" and context.installed_language_runtime < "7.0")
    @irrelevant(context.library == "python" and context.installed_language_runtime < "3.7.0")
    @irrelevant(context.library == "nodejs" and context.installed_language_runtime < "17.0")
    @bug(context.library == "python@2.19.1", reason="INPLAT-448")
    @irrelevant(context.weblog_variant == "js-command-line")
    def test_telemetry(self):
        # There is telemetry data about the auto instrumentation injector. We only validate there is data
        telemetry_autoinject_data = interfaces.test_agent.get_telemetry_for_autoinject()
        assert len(telemetry_autoinject_data) >= 1
        inject_success = False
        for data in telemetry_autoinject_data:
            if data["metric"] == "inject.success":
                inject_success = True
                break
        assert inject_success, "No telemetry data found for inject.success"

        # There is telemetry data about the library entrypoint. We only validate there is data
        telemetry_autoinject_data = interfaces.test_agent.get_telemetry_for_autoinject_library_entrypoint()
        assert len(telemetry_autoinject_data) >= 1
        inject_success = False
        for data in telemetry_autoinject_data:
            if data["metric"] == "library_entrypoint.complete":
                inject_success = True
                break
        assert inject_success, "No telemetry data found for library_entrypoint.complete"

    @features.ssi_guardrails
    @irrelevant(context.library == "java" and context.installed_language_runtime >= "1.8.0_0")
    @irrelevant(context.library == "php" and context.installed_language_runtime >= "7.0")
    @irrelevant(context.library == "python" and context.installed_language_runtime >= "3.7.0")
    @bug(context.library == "nodejs" and context.installed_language_runtime < "12.17.0", reason="INPLAT-252")
    @bug(context.library == "java" and context.installed_language_runtime == "1.7.0-201", reason="INPLAT-427")
    @irrelevant(context.library == "nodejs" and context.installed_language_runtime >= "17.0")
    @irrelevant(context.weblog_variant == "js-command-line")
    def test_telemetry_abort(self):
        # There is telemetry data about the auto instrumentation injector. We only validate there is data
        telemetry_autoinject_data = interfaces.test_agent.get_telemetry_for_autoinject()
        assert len(telemetry_autoinject_data) >= 1
        inject_result = None
        for data in telemetry_autoinject_data:
            if data["metric"] == "inject.success":
                inject_result = True
                break
            if data["metric"] == "inject.skip" or data["metric"] == "inject.error":
                inject_result = False
                break

        assert inject_result != None, "No telemetry data found for inject.success, inject.skip or inject.error"

        # The injector detected by itself that the version is not supported
        if inject_result == False:
            return

        # There is telemetry data about the library entrypoint. We only validate there is data
        telemetry_autoinject_data = interfaces.test_agent.get_telemetry_for_autoinject_library_entrypoint()
        assert len(telemetry_autoinject_data) >= 1
        abort = False
        for data in telemetry_autoinject_data:
            if data["metric"] == "library_entrypoint.abort":
                abort = True
                break
        assert abort, "No telemetry data found for library_entrypoint.abort"

    def setup_service_name(self):
        self._setup_all()

    @features.ssi_service_naming
    @irrelevant(condition=not context.weblog_variant.startswith("tomcat-app"))
    @irrelevant(condition=not context.weblog_variant.startswith("websphere-app"))
    @irrelevant(condition=not context.weblog_variant.startswith("jboss-app"))
    def test_service_name(self):
        logger.info("Testing Docker SSI service name")
        # There are traces related with the request and the service name is payment-service
        traces_for_request = interfaces.test_agent.get_traces(request=self.r)
        assert traces_for_request, f"No traces found for request {get_rid_from_request(self.r)}"
        assert "service" in traces_for_request, "No service name found in traces"
        assert (
            traces_for_request["service"] == "payment-service"
        ), f"Service name is not payment-service but {traces_for_request['service']}"


@scenarios.docker_ssi
class TestPoC:
    _weblog_container = None

    def setup_all(self):
        """look for the weblog container and store in a class variable"""
        if self._weblog_container:
            return

        for container in context.scenario._required_containers:
            if isinstance(container, DockerSSIContainer):
                self._weblog_container = container
                break

    def setup_folder_structure(self):
        self.setup_all()

    def setup_poc(self):
        self.setup_all()

    @features.ssi_guardrails
    def test_folder_structure(self):
        check_folder_command = "sh -c '[ -d \"/opt/datadog-packages/datadog-apm-inject/\" ] && echo true || echo false'"
        check_folder_command_out = self._weblog_container.execute_command(
            check_folder_command, environment={"DD_APM_INSTRUMENTATION_DEBUG": "false"}
        )
        assert check_folder_command_out[1].strip() == "true", "Folder structure is not as expected"

    @features.ssi_guardrails
    def test_poc(self):
        my_command_output = self._weblog_container.execute_command("ls -la /opt/datadog-packages/")
        # Use utils/interfaces/_test_agent.py _TestAgentInterfaceValidator to get traces and telemetry data
        # and make your own assertions
        # use interfaces.test_agent.
        assert my_command_output, "No output from command"
