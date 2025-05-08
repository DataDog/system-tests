from urllib.parse import urlparse

from utils import scenarios, features, context, irrelevant, bug, interfaces, weblog, logger, missing_feature


@scenarios.docker_ssi
class TestDockerSSIFeatures:
    """Test the ssi in a simulated host injection environment (docker container + test agent)
    We test that the injection is performed and traces and telemetry are generated.
    If the language version is not supported, we only check that we don't break the app and telemetry is generated.
    """

    _r = None

    def _setup_all(self):
        if TestDockerSSIFeatures._r is None:
            parsed_url = urlparse(scenarios.docker_ssi.weblog_url)
            logger.info(f"Setting up Docker SSI installation WEBLOG_URL {scenarios.docker_ssi.weblog_url}")
            TestDockerSSIFeatures._r = weblog.request(
                "GET", parsed_url.path, domain=parsed_url.hostname, port=parsed_url.port
            )
            logger.info(f"Setup Docker SSI installation {TestDockerSSIFeatures._r}")

        self.r = TestDockerSSIFeatures._r

    def setup_install_supported_runtime(self):
        self._setup_all()

    @features.ssi_guardrails
    @bug(condition="centos-7" in context.weblog_variant and context.library == "java", reason="APMON-1490")
    @irrelevant(context.library == "java" and context.installed_language_runtime < "1.8.0_0")
    @irrelevant(context.library == "php" and context.installed_language_runtime < "7.0")
    @irrelevant(context.library == "nodejs" and context.installed_language_runtime < "17.0")
    def test_install_supported_runtime(self):
        logger.info(f"Testing Docker SSI installation on supported lang runtime: {context.library}")
        assert self.r.status_code == 200, f"Failed to get response from {scenarios.docker_ssi.weblog_url}"

        # If the language version is supported there are traces related with the request
        traces_for_request = interfaces.test_agent.get_traces(request=self.r)
        assert traces_for_request, f"No traces found for request {self.r.get_rid()}"
        assert "runtime-id" in traces_for_request["meta"], "No runtime-id found in traces"

        # There is telemetry data related with the runtime-id
        telemetry_data = interfaces.test_agent.get_telemetry_for_runtime(traces_for_request["meta"]["runtime-id"])
        assert telemetry_data, "No telemetry data found"

    def setup_install_weblog_running(self):
        self._setup_all()

    @features.ssi_guardrails
    @bug(
        condition="centos-7" in context.weblog_variant and context.library == "java",
        reason="APMON-1490",
    )
    def test_install_weblog_running(self):
        logger.info(f"Testing Docker SSI installation. The weblog should be running: {context.library}")
        assert self.r.status_code == 200, f"Failed to get response from {scenarios.docker_ssi.weblog_url}"

    @features.ssi_guardrails
    @bug(
        condition="centos-7" in context.weblog_variant and context.library == "java",
        reason="APMON-1490",
    )
    @irrelevant(context.library == "java" and context.installed_language_runtime < "1.8.0_0")
    @irrelevant(context.library == "php" and context.installed_language_runtime < "7.0")
    @irrelevant(context.library == "python" and context.installed_language_runtime < "3.7.0")
    @irrelevant(context.library == "nodejs" and context.installed_language_runtime < "17.0")
    @bug(context.library == "python@2.19.1", reason="INPLAT-448")
    @bug(context.library >= "python@3.0.0dev", reason="INPLAT-448")
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

        assert inject_result is not None, "No telemetry data found for inject.success, inject.skip or inject.error"

        # The injector detected by itself that the version is not supported
        if inject_result is False:
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
    @irrelevant(
        condition=not context.weblog_variant.startswith("tomcat-app")
        and not context.weblog_variant.startswith("websphere-app")
        and not context.weblog_variant.startswith("jboss-app")
    )
    def test_service_name(self):
        logger.info("Testing Docker SSI service name")
        # There are traces related with the request and the service name is payment-service
        traces_for_request = interfaces.test_agent.get_traces(request=self.r)
        assert traces_for_request, f"No traces found for request {self.r.get_rid()}"
        assert "service" in traces_for_request, "No service name found in traces"
        assert (
            traces_for_request["service"] == "payment-service"
        ), f"Service name is not payment-service but {traces_for_request['service']}"

    def setup_instrumentation_source_ssi(self):
        self._setup_all()

    @features.ssi_service_tracking
    @missing_feature(context.library in ("nodejs", "dotnet", "java", "php", "ruby"), reason="Not implemented yet")
    @missing_feature(context.library < "python@3.8.0.dev", reason="INPLAT-448")
    def test_instrumentation_source_ssi(self):
        logger.info("Testing Docker SSI service tracking")
        # There are traces related with the request
        root_span = interfaces.test_agent.get_traces(request=self.r)
        assert root_span, f"No traces found for request {self.r.get_rid()}"
        assert "service" in root_span, f"No service name found in root_span: {root_span}"
        # Get all captured telemetry configuration data
        configurations = interfaces.test_agent.get_telemetry_configurations(
            root_span["service"], root_span["meta"]["runtime-id"]
        )

        # Check that instrumentation source is ssi
        injection_source = configurations.get("instrumentation_source")
        assert injection_source, f"instrumentation_source not found in configuration {configurations}"
        assert injection_source["value"] == "ssi", f"instrumentation_source value is not ssi {injection_source}"
