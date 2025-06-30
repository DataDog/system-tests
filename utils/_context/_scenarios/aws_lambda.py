import os
import pytest
from utils import interfaces
from utils._context._scenarios.core import ScenarioGroup
from utils._context.containers import LambdaProxyContainer, LambdaWeblogContainer
from utils._logger import logger
from .endtoend import DockerScenario, ProxyBasedInterfaceValidator


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
        agent_interface_timeout: int = 5,
        backend_interface_timeout: int = 0,
        library_interface_timeout: int | None = None,
        use_proxy_for_weblog: bool = True,
        use_proxy_for_agent: bool = True,
        require_api_key: bool = False,
        weblog_env: dict[str, str | None] | None = None,
        weblog_volumes: dict[str, dict[str, str]] | None = None,
    ):
        use_proxy = use_proxy_for_weblog or use_proxy_for_agent
        self._require_api_key = require_api_key

        super().__init__(
            name, github_workflow=github_workflow, doc=doc, use_proxy=use_proxy, scenario_groups=scenario_groups
        )

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

        if use_proxy:
            self.lambda_weblog.depends_on.append(self.proxy_container)

        if use_proxy_for_agent:
            self.proxy_container.environment.update(
                {
                    "PROXY_TRACING_AGENT_TARGET_HOST": self.lambda_weblog.name,
                    "PROXY_TRACING_AGENT_TARGET_PORT": "8126",
                }
            )

        self._required_containers.extend((self.lambda_weblog, self.lambda_proxy_container))

        self.agent_interface_timeout = agent_interface_timeout
        self.backend_interface_timeout = backend_interface_timeout
        self._library_interface_timeout = library_interface_timeout

    def configure(self, config: pytest.Config):
        super().configure(config)

        if self._require_api_key and "DD_API_KEY" not in os.environ and not self.replay:
            pytest.exit("DD_API_KEY is required for this scenario", 1)

        if config.option.force_dd_trace_debug:
            self.lambda_weblog.environment["DD_TRACE_DEBUG"] = "true"

        if config.option.force_dd_iast_debug:
            self.lambda_weblog.environment["_DD_IAST_DEBUG"] = "true"  # probably not used anymore ?
            self.lambda_weblog.environment["DD_IAST_DEBUG_ENABLED"] = "true"

        if config.option.force_dd_trace_debug:
            self.lambda_weblog.environment["DD_TRACE_DEBUG"] = "true"

        interfaces.agent.configure(self.host_log_folder, replay=self.replay)
        interfaces.library.configure(self.host_log_folder, replay=self.replay)
        interfaces.backend.configure(self.host_log_folder, replay=self.replay)
        interfaces.library_dotnet_managed.configure(self.host_log_folder, replay=self.replay)
        interfaces.library_stdout.configure(self.host_log_folder, replay=self.replay)
        interfaces.agent_stdout.configure(self.host_log_folder, replay=self.replay)

        library = self.lambda_weblog.image.labels["system-tests-library"]

        if self._library_interface_timeout is None:
            if library == "java":
                self.library_interface_timeout = 25
            elif library in ("golang",):
                self.library_interface_timeout = 10
            elif library in ("nodejs", "ruby"):
                self.library_interface_timeout = 0
            elif library in ("php",):
                self.library_interface_timeout = 10
            elif library in ("python",):
                self.library_interface_timeout = 5
            else:
                self.library_interface_timeout = 40
        else:
            self.library_interface_timeout = self._library_interface_timeout

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
            self._wait_interface(
                interfaces.library, 0 if force_interface_timeout_to_zero else self.library_interface_timeout
            )

            self.lambda_weblog.stop()
            interfaces.library.check_deserialization_errors()

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
