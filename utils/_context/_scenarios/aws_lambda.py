import pytest
from utils import interfaces
from utils.interfaces._core import ProxyBasedInterfaceValidator
from ._core import DockerScenario, scenario_groups, scenario_groups as all_scenario_groups, ScenarioGroup
from utils._context.constants import WeblogCategory
from utils._context.containers import LambdaProxyContainer, LambdaWeblogContainer, InternalServerContainer
from utils._logger import logger


class _LambdaScenario(DockerScenario):
    """Scenario for end-to-end testing of AWS Lambda HTTP Instrumentation.

    The `_LambdaScenario` sets up an environment with the following components:
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
        trace_managed_services: bool = False,
    ):
        scenario_groups = [
            all_scenario_groups.tracer_release,
            all_scenario_groups.end_to_end,
            all_scenario_groups.lambda_end_to_end,
            all_scenario_groups.all,
        ] + (scenario_groups or [])

        super().__init__(
            name,
            github_workflow=github_workflow,
            doc=doc,
            scenario_groups=scenario_groups,
            weblog_categories=[WeblogCategory.dd_trace_lambda],
        )

        self.lambda_weblog = LambdaWeblogContainer(
            environment=weblog_env or {}, volumes=weblog_volumes or {}, trace_managed_services=trace_managed_services
        )

        self.lambda_proxy_container = LambdaProxyContainer(
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

        self._containers.extend((self.lambda_weblog, self.lambda_proxy_container))

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
        interfaces.library_stdout.configure(self.host_log_folder, replay=self.replay)

        if not self.replay:
            self.warmups.insert(1, self._start_interfaces_watchdog)
            self.warmups.append(self._get_weblog_system_info)
            self.warmups.append(self._wait_for_app_readiness)
        self.warmups.append(self._set_components)

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
        self.components["library"] = self.library.version
        self.components[self.library.name] = self.library.version

    def _wait_for_app_readiness(self):
        logger.debug("Wait for app readiness")

        if not interfaces.library.ready.wait(40):
            raise ValueError("Library not ready")

        logger.debug("Library ready")

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
        else:
            self._wait_interface(interfaces.library, 0 if force_interface_timeout_to_zero else 5)
            self._wait_interface(interfaces.agent, 0 if force_interface_timeout_to_zero else 5)
            self.lambda_weblog.stop()
            interfaces.library.check_deserialization_errors()
            interfaces.agent.check_deserialization_errors()

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

    def get_junit_properties(self) -> dict[str, dict[str, str] | str]:
        result = super().get_junit_properties()

        result["library"] = {"name": self.library.name, "version": str(self.library.version)}
        result["weblog_variant"] = self.weblog_variant

        return result


# Appsec Lambda Scenarios
class AppsecLambdaDefault(_LambdaScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_LAMBDA_DEFAULT",
            doc="Default Lambda scenario",
            scenario_groups=[scenario_groups.appsec, scenario_groups.appsec_lambda],
        )


class AppsecLambdaBlocking(_LambdaScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_LAMBDA_BLOCKING",
            weblog_env={"DD_APPSEC_RULES": "/appsec_blocking_rule.json"},
            weblog_volumes={"./tests/appsec/blocking_rule.json": {"bind": "/appsec_blocking_rule.json", "mode": "ro"}},
            doc="Misc tests for appsec blocking in Lambda",
            scenario_groups=[scenario_groups.appsec, scenario_groups.appsec_lambda],
        )


class AppsecLambdaApiSecurity(_LambdaScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_LAMBDA_API_SECURITY",
            weblog_env={
                "DD_API_SECURITY_ENABLED": "true",
                "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0",
                "DD_API_SECURITY_SAMPLE_DELAY": "0.0",
                "DD_API_SECURITY_ENDPOINT_COLLECTION_ENABLED": "true",
                "DD_API_SECURITY_ENDPOINT_COLLECTION_MESSAGE_LIMIT": "30",
            },
            doc="""
        Scenario for API Security feature in lambda, testing schema types sent into span tags if
        DD_API_SECURITY_ENABLED is set to true.
        """,
            scenario_groups=[scenario_groups.appsec, scenario_groups.appsec_lambda],
        )


class AppsecLambdaRasp(_LambdaScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_LAMBDA_RASP",
            weblog_env={
                "DD_APPSEC_RASP_ENABLED": "true",
                "DD_APPSEC_RULES": "/appsec_rasp_ruleset.json",
                # added to test Test_ExtendedRequestBodyCollection
                "DD_APPSEC_RASP_COLLECT_REQUEST_BODY": "true",
                "DD_API_SECURITY_DOWNSTREAM_BODY_ANALYSIS_SAMPLE_RATE": "1.0",
            },
            weblog_volumes={
                "./tests/appsec/rasp/rasp_ruleset.json": {"bind": "/appsec_rasp_ruleset.json", "mode": "ro"}
            },
            doc="Enable APPSEC RASP",
            github_workflow="endtoend",
            scenario_groups=[
                scenario_groups.appsec_rasp,
                scenario_groups.appsec_rasp_scenario,
                scenario_groups.appsec_lambda,
            ],
        )

    def configure(self, config: pytest.Config):
        self._internal_server = InternalServerContainer()
        self.lambda_weblog.depends_on.append(self._internal_server)
        self._containers.append(self._internal_server)

        super().configure(config)


class AppsecLambdaInferredSpans(_LambdaScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_LAMBDA_INFERRED_SPANS",
            doc="Lambda scenario with managed services tracing enabled",
            scenario_groups=[scenario_groups.appsec, scenario_groups.appsec_lambda],
            trace_managed_services=True,
        )
