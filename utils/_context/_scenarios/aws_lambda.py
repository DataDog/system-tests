import pytest
from utils import interfaces
from utils._context._scenarios.core import ScenarioGroup
from utils._context.containers import LambdaProxyContainer, LambdaWeblogContainer
from utils._logger import logger
from .endtoend import DockerScenario, ProxyBasedInterfaceValidator
from .core import scenario_groups as all_scenario_groups


class LambdaScenario(DockerScenario):
    """Scenario for end-to-end testing of AWS Lambda HTTP Instrumentation.

    The `LambdaScenario` sets up an environment with the following components:
    - A LambdaWeblog container that runs the application using AWS Lambda RIE (Runtime Interface Emulator).
    - A LambdaProxy container that converts between http requests and lambda events to invoke the function.

    In this scenario, there is no agent container, but the LambdaWeblog contains the `datadog-lambda-extension`
    which is the agent in the context of Lambda.
    """

    def __init__(
        self,
        name: str,
        *,
        github_workflow: str = "endtoend",
        doc: str,
        scenario_groups: list[ScenarioGroup] | None = None,
        weblog_env: dict[str, str | None] | None = None,
        weblog_volumes: dict[str, dict[str, str]] | None = None,
    ):
        scenario_groups = [
            all_scenario_groups.tracer_release,
            all_scenario_groups.end_to_end,
            all_scenario_groups.lambda_end_to_end,
        ] + (scenario_groups or [])

        super().__init__(name, github_workflow=github_workflow, doc=doc, scenario_groups=scenario_groups)

        self.lambda_weblog = LambdaWeblogContainer(
            host_log_folder=self.host_log_folder,
            environment=weblog_env or {},
            volumes=weblog_volumes or {},
        )

        self.lambda_proxy_container = LambdaProxyContainer(
            host_log_folder=self.host_log_folder,
            lambda_weblog_host=self.lambda_weblog.name,
            lambda_weblog_port=str(self.lambda_weblog.container_port),
        )

        self.lambda_proxy_container.depends_on.append(self.lambda_weblog)
        self.lambda_weblog.depends_on.append(self.proxy_container)

        self.proxy_container.environment.update(
            {
                "PROXY_TRACING_AGENT_TARGET_HOST": self.lambda_weblog.name,
                "PROXY_TRACING_AGENT_TARGET_PORT": "8127",
            }
        )

        self._required_containers.extend((self.lambda_weblog, self.lambda_proxy_container))

    def configure(self, config: pytest.Config):
        super().configure(config)

        allowed_event_types = (
            "apigateway-rest",
            "apigateway-http",
            "function-url",
            "application-load-balancer",
            "application-load-balancer-multi",
        )
        event_type = self.lambda_weblog.image.labels.get("system-tests.lambda-proxy.event-type")
        if event_type not in allowed_event_types:
            pytest.exit(
                "In lambda scenarios, the weblog image must contain the variable `LAMBDA_EVENT_TYPE`"
                f" with a value in {allowed_event_types}",
            )

        self.lambda_proxy_container.environment.update({"LAMBDA_EVENT_TYPE": event_type})

        interfaces.agent.configure(self.host_log_folder, replay=self.replay)
        interfaces.library.configure(self.host_log_folder, replay=self.replay)
        interfaces.backend.configure(self.host_log_folder, replay=self.replay)
        interfaces.library_stdout.configure(self.host_log_folder, replay=self.replay)

    def _get_weblog_system_info(self):
        try:
            code, (stdout, stderr) = self.lambda_weblog.exec_run("uname -a", demux=True)
            if code or stdout is None:
                message = f"Failed to get weblog system info: [{code}] {stderr.decode()} {stdout.decode()}"
            else:
                message = stdout.decode()
        except BaseException:
            logger.exception("can't get weblog system info")
        else:
            logger.stdout(f"Weblog system: {message.strip()}")

        if self.lambda_weblog.environment.get("DD_TRACE_DEBUG") == "true":
            logger.stdout("\t/!\\ Debug logs are activated in weblog")

        logger.stdout("")

    def _start_interfaces_watchdog(self):
        return super().start_interfaces_watchdog([interfaces.library, interfaces.agent])

    def _set_components(self):
        self.components["libary"] = self.library.version

    def _wait_for_app_readiness(self):
        logger.debug("Wait for app readiness")

        if not interfaces.library.ready.wait(40):
            raise ValueError("Library not ready")

        logger.debug("Library ready")

    def get_warmups(self):
        warmups = super().get_warmups()

        if not self.replay:
            warmups.insert(1, self._start_interfaces_watchdog)
            warmups.append(self._get_weblog_system_info)
            warmups.append(self._wait_for_app_readiness)
            warmups.append(self._set_components)

        return warmups

    def _wait_interface(self, interface: ProxyBasedInterfaceValidator, timeout: int):
        logger.terminal.write_sep("-", f"Wait for {interface.name} interface ({timeout}s)")
        logger.terminal.flush()

        interface.wait(timeout)

    def _wait_and_stop_containers(self, *, force_interface_timeout_to_zero: bool = False):
        if self.replay:
            logger.terminal.write_sep("-", "Load all data from logs")
            logger.terminal.flush()

            interfaces.library.load_data_from_logs()
            interfaces.library.check_deserialization_errors()

            interfaces.backend.load_data_from_logs()
        else:
            self._wait_interface(interfaces.library, 0 if force_interface_timeout_to_zero else 5)
            self._wait_interface(interfaces.agent, 0 if force_interface_timeout_to_zero else 5)
            self.lambda_weblog.stop()
            interfaces.library.check_deserialization_errors()
            interfaces.agent.check_deserialization_errors()

            self._wait_interface(interfaces.backend, 0)

    def post_setup(self, session: pytest.Session):
        is_empty_test_run = session.config.option.skip_empty_scenario and len(session.items) == 0

        try:
            self._wait_and_stop_containers(force_interface_timeout_to_zero=is_empty_test_run)
        finally:
            self.close_targets()

    @property
    def library(self):
        return self.lambda_weblog.library

    @property
    def weblog_variant(self):
        return self.lambda_weblog.weblog_variant

    def get_junit_properties(self) -> dict[str, str]:
        result = super().get_junit_properties()

        result["dd_tags[systest.suite.context.library.name]"] = self.library.name
        result["dd_tags[systest.suite.context.library.version]"] = self.library.version
        result["dd_tags[systest.suite.context.weblog_variant]"] = self.weblog_variant

        return result
