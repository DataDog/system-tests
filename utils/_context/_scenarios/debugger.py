import pytest

from utils._logger import logger
from utils._context.constants import WeblogCategory

from ._core import DdTraceEndToEndScenario, EndToEndScenario, scenario_groups


class _DebuggerScenario(EndToEndScenario):
    def __init__(self, name: str, doc: str, weblog_env: dict[str, str | None]) -> None:
        base_weblog_env: dict[str, str | None] = {
            "DD_REMOTE_CONFIG_ENABLED": "1",
            "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
            # added temporarily to troubleshoot debugger test flakiness
            "JAVA_OPTS": " -Ddatadog.slf4j.simpleLogger.log.com.datadog.debugger=debug ",
        }

        base_weblog_env.update(weblog_env)

        super().__init__(
            name=name,
            doc=doc,
            rc_api_enabled=True,
            rc_backend_enabled=True,
            library_interface_timeout=5,
            weblog_env=base_weblog_env,
            scenario_groups=[scenario_groups.debugger],
            weblog_categories=[WeblogCategory.dd_trace],
        )

    def configure(self, config: pytest.Config):
        super().configure(config)

        library = self.weblog_infra.library_name
        if library == "php":
            # Disable appsec for PHP debugger tests so appsec-specific span tags don't
            # appear in snapshot comparisons, which were generated without appsec.
            self.weblog_container.environment["DD_APPSEC_ENABLED"] = "0"
        if library == "python":
            # Python v4.0+ only recognizes UPLOAD_INTERVAL_SECONDS, while v3.9 and
            # earlier only recognizes UPLOAD_FLUSH_INTERVAL (both use seconds as the
            # unit). Set both so it works regardless of the Python tracer version.
            self.weblog_container.environment["DD_DYNAMIC_INSTRUMENTATION_UPLOAD_INTERVAL_SECONDS"] = "0.1"
            self.weblog_container.environment["DD_DYNAMIC_INSTRUMENTATION_UPLOAD_FLUSH_INTERVAL"] = "0.1"
        elif library == "nodejs":
            self.weblog_container.environment["DD_DYNAMIC_INSTRUMENTATION_UPLOAD_INTERVAL_SECONDS"] = "0.1"
        elif library in ("java", "dotnet"):
            # Java and .NET use UPLOAD_FLUSH_INTERVAL in milliseconds
            self.weblog_container.environment["DD_DYNAMIC_INSTRUMENTATION_UPLOAD_FLUSH_INTERVAL"] = "100"
        if library == "golang":
            # The Go debugger is primarily implemented in the system-probe, so
            # make sure to mount the system-probe.yaml file so that the
            # system-probe sub-agent is launched and runs with the correct
            # configuration.
            self.agent_container.volumes["./utils/build/docker/agent/system-probe.yaml"] = {
                "bind": "/etc/datadog-agent/system-probe.yaml",
                "mode": "ro",
            }
            # The system-probe needs to be privileged to be able to attach to
            # the processes and read the memory.
            self.agent_container.privileged = True
            self.agent_container.pid_mode = "host"
            # Additionally, the system-probe needs to be able to access the
            # kernel debug and cgroup filesystems so that it can discover
            # process container information and load bpf programs.
            #
            # Docker for mac magically does the right thing to make this work
            # when run from macOS as well.
            self.agent_container.volumes["/sys/kernel/debug"] = {"bind": "/sys/kernel/debug", "mode": "ro"}
            self.agent_container.volumes["/sys/fs/cgroup"] = {"bind": "/sys/fs/cgroup", "mode": "ro"}
            # Set the system-probe to output to the proxy the same way the
            # libraries are being told to. For golang, the system-probe acts
            # as a tracer library and sends data to the trace-agent just like
            # the other libraries.
            weblog_env = self.weblog_container.environment
            self.agent_container.environment["DD_TRACE_AGENT_PORT"] = weblog_env["DD_TRACE_AGENT_PORT"]
            self.agent_container.environment["DD_AGENT_HOST"] = weblog_env["DD_AGENT_HOST"]

        if not self.replay:
            self.warmups.append(self._wait_for_agent_debugging)

    def _wait_for_agent_debugging(self) -> None:
        logger.stdout("Wait for /debugger/v1/diagnostics endpoint on agent")

        container = self.agent_container
        exit_code, output = container.execute_command(
            "curl "
            "--fail --silent --show-error --max-time 2 "
            '-X POST -H "Content-Type: application/json" '
            "-d '[]' "
            f"http://localhost:{container.apm_receiver_port}/debugger/v1/diagnostics"
        )
        if exit_code != 0:
            logger.stdout(f"Agent debugger endpoint Healthcheck failed:\n{output}")
            pytest.exit("Agent failed to start")


class DebuggerProbesSnapshot(_DebuggerScenario):
    def __init__(self) -> None:
        super().__init__(
            "DEBUGGER_PROBES_SNAPSHOT",
            weblog_env={
                # Required by Node.js to ensure the snapshot isn't truncated due to a timeout
                "DD_DYNAMIC_INSTRUMENTATION_CAPTURE_TIMEOUT_MS": "1000",
                "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
                "DD_CODE_ORIGIN_FOR_SPANS_ENABLED": "1",
                "DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED": "true",
            },
            doc="Test scenario for checking if debugger successfully generates snapshots for probes",
        )


class DebuggerCaptureTimeout(_DebuggerScenario):
    def __init__(self) -> None:
        super().__init__(
            "DEBUGGER_CAPTURE_TIMEOUT",
            weblog_env={
                "DD_DYNAMIC_INSTRUMENTATION_CAPTURE_TIMEOUT": "10",
                "DD_DYNAMIC_INSTRUMENTATION_CAPTURE_TIMEOUT_MS": "10",
                "DD_DYNAMIC_INSTRUMENTATION_MAX_TIME_TO_SERIALIZE": "10",
                "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
            },
            doc="Test that debugger snapshot capture reports when its time budget is exceeded",
        )


class DebuggerEvaluationTimeout(_DebuggerScenario):
    def __init__(self) -> None:
        super().__init__(
            "DEBUGGER_EVALUATION_TIMEOUT",
            weblog_env={
                "DD_DYNAMIC_INSTRUMENTATION_EVALUATION_TIMEOUT": "10",
                "DD_DYNAMIC_INSTRUMENTATION_EVALUATION_TIMEOUT_MS": "10",
                "DD_DYNAMIC_INSTRUMENTATION_MAX_TIME_TO_EVALUATE": "10",
                "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
            },
            doc="Test that debugger expression evaluation reports when its time budget is exceeded",
        )


class DebuggerProbesSnapshotWithScm(_DebuggerScenario):
    def __init__(self) -> None:
        super().__init__(
            "DEBUGGER_PROBES_SNAPSHOT_WITH_SCM",
            weblog_env={
                "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
                "DD_CODE_ORIGIN_FOR_SPANS_ENABLED": "1",
                "DD_GIT_REPOSITORY_URL": "https://github.com/datadog/hello",
                "DD_GIT_COMMIT_SHA": "1234hash",
            },
            doc="Test scenario for checking if debugger successfully generates SCM metadata in snapshots for probes",
        )


class DebuggerPiiRedaction(_DebuggerScenario):
    def __init__(self) -> None:
        super().__init__(
            "DEBUGGER_PII_REDACTION",
            weblog_env={
                # Required by Node.js to ensure the snapshot isn't truncated due to a timeout
                "DD_DYNAMIC_INSTRUMENTATION_CAPTURE_TIMEOUT_MS": "1000",
                "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
                "DD_DYNAMIC_INSTRUMENTATION_REDACTED_TYPES": "weblog.Models.Debugger.CustomPii,com.datadoghq.system_tests.springboot.debugger.CustomPii,CustomPii",  # noqa: E501
                "DD_DYNAMIC_INSTRUMENTATION_REDACTED_IDENTIFIERS": "customidentifier1,customidentifier2",
            },
            doc="Check pii redaction",
        )


class DebuggerExpressionLanguage(_DebuggerScenario):
    def __init__(self) -> None:
        super().__init__(
            "DEBUGGER_EXPRESSION_LANGUAGE",
            weblog_env={
                "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
            },
            doc="Check expression language",
        )


class DebuggerExceptionReplay(_DebuggerScenario):
    def __init__(self) -> None:
        super().__init__(
            "DEBUGGER_EXCEPTION_REPLAY",
            weblog_env={
                "DD_EXCEPTION_REPLAY_ENABLED": "1",
                "DD_CODE_ORIGIN_FOR_SPANS_ENABLED": "0",
                "DD_EXCEPTION_REPLAY_CAPTURE_MAX_FRAMES": "10",
                # Avoid flaky captures being truncated by the default 150ms capture timeout under CI load
                "DD_DYNAMIC_INSTRUMENTATION_CAPTURE_TIMEOUT_MS": "1000",
            },
            doc="Check exception replay",
        )


class DebuggerSymdb(_DebuggerScenario):
    def __init__(self) -> None:
        super().__init__(
            "DEBUGGER_SYMDB",
            weblog_env={
                "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
                "DD_SYMBOL_DATABASE_UPLOAD_ENABLED": "1",
            },
            doc="Test scenario for checking symdb.",
        )


class DebuggerInproductEnablement(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "DEBUGGER_INPRODUCT_ENABLEMENT",
            rc_api_enabled=True,
            rc_backend_enabled=False,
            weblog_env={
                "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.1",
                "DD_TRACE_FLUSH_INTERVAL": "100",
            },
            library_interface_timeout=5,
            doc="Test scenario for checking dynamic enablement.",
            scenario_groups=[scenario_groups.debugger],
        )


class DebuggerTelemetry(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "DEBUGGER_TELEMETRY",
            mocked_backend=True,
            use_proxy_for_agent=False,
            weblog_env={
                "DD_REMOTE_CONFIG_ENABLED": "true",
                "DD_CODE_ORIGIN_FOR_SPANS_ENABLED": "1",
                "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
                "DD_EXCEPTION_REPLAY_ENABLED": "1",
                "DD_SYMBOL_DATABASE_UPLOAD_ENABLED": "1",
            },
            library_interface_timeout=5,
            doc="Test scenario for checking debugger telemetry.",
            scenario_groups=[scenario_groups.debugger, scenario_groups.telemetry],
        )
