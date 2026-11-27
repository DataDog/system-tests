from urllib.parse import urlparse

from utils import scenarios, features, context, interfaces, weblog, logger


@features.ssi_guardrails
@scenarios.docker_ssi_guardrail
class Test_DockerSSIGuardrail:
    """The application runs on a runtime that the tracer does not support.
    SSI must keep the application working, must not instrument it, and the tracer must report why it aborted.
    """

    def setup_unsupported_runtime_not_instrumented(self):
        parsed_url = urlparse(scenarios.docker_ssi_guardrail.weblog_url)
        self.r = weblog.request("GET", parsed_url.path, domain=parsed_url.hostname, port=parsed_url.port)

    def test_unsupported_runtime_not_instrumented(self):
        logger.info(f"Testing SSI guardrail for {context.library} on runtime {context.installed_language_runtime}")
        assert self.r.status_code == 200, f"SSI broke the application: {self.r.status_code}"

        assert interfaces.test_agent.get_traces(request=self.r) is None, "SSI instrumented an unsupported runtime"

        # The abort telemetry proves that SSI tried to inject and the tracer withdrew for the right reason
        abort_reasons = [
            tag
            for series in interfaces.test_agent.get_telemetry_for_autoinject_library_entrypoint()
            if series["metric"] == "library_entrypoint.abort"
            for tag in series.get("tags", [])
            if tag.startswith("reason:")
        ]
        assert "reason:incompatible_runtime" in abort_reasons, f"No abort telemetry for the runtime: {abort_reasons}"
