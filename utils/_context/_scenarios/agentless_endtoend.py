from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any, Literal, cast

from docker.models.containers import Container
import pytest

from utils import interfaces
from utils._context.containers import ServerlessInitContainer, TestedContainer
from utils._context.docker import get_docker_client
from utils.docker_fixtures._core import extra_hosts_for_environment
from utils._logger import logger
from utils._weblog import weblog
from utils.mocked_backend.ffe import (
    EXPECTED_API_KEY,
    MockFFEAgentlessBackendServer,
    MockFFEAgentlessBackendStatus,
)
from utils.proxy.ports import ProxyPorts

from .core import ScenarioGroup, scenario_groups as all_scenario_groups
from .endtoend import DdTraceEndToEndScenario

if TYPE_CHECKING:
    from utils.interfaces._core import ProxyBasedInterfaceValidator


DIRECT_EVP_CA_BUNDLE_SOURCE = "./utils/build/docker/agent/ca-certificates.crt"
DIRECT_EVP_CA_BUNDLE_CONTAINER_PATH = "/etc/ssl/certs/ca-certificates.crt"
DIRECT_EVP_SIGNAL_PATHS = frozenset({"/api/v2/exposures", "/api/v2/flagevaluation"})
DIRECT_EVP_CAPTURE_WAIT_SECONDS = 30
DIRECT_EVP_CAPTURE_SETTLE_SECONDS = 3
DIRECT_EVP_RUNTIME_EVIDENCE_FILENAME = "direct_evp_runtime.json"
DIRECT_EVP_SHUTDOWN_EVIDENCE_FILENAME = "direct_evp_shutdown.json"
DIRECT_EVP_STOP_TIMEOUT_SECONDS = 10
DIRECT_EVP_SHUTDOWN_BOUND_SECONDS = DIRECT_EVP_STOP_TIMEOUT_SECONDS + 2
DIRECT_EVP_SHUTDOWN_MARKER_EVENT = "system_tests.ffe.shutdown.server_closed"
DIRECT_EVP_AGENT_VARIABLES = (
    "DD_AGENT_HOST",
    "DD_DOGSTATSD_HOST",
    "DD_DOGSTATSD_PORT",
    "DD_DOGSTATSD_URL",
    "DD_TRACE_AGENT_HOSTNAME",
    "DD_TRACE_AGENT_PORT",
    "DD_TRACE_AGENT_URL",
)
DIRECT_EVP_SHUTDOWN_FLUSH_ENV = "SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED"


@dataclass(frozen=True)
class DirectEVPShutdownEvaluation:
    """One evaluation deferred until the scenario-owned shutdown-flush phase."""

    signal_path: str
    request_path: str
    body: dict[str, Any]
    flag_key: str
    subject_id: str


class AgentlessEndToEndScenario(DdTraceEndToEndScenario):
    """End-to-end scenario without a Datadog Agent, using agentless delivery mechanisms."""

    _default_scenario_groups: tuple[ScenarioGroup, ...] = ()  # exclude those scenario from tracer_release
    _mock_backend_status_filename = "mock_agentless_backend_status.json"

    _mock_backend: MockFFEAgentlessBackendServer | None = None
    _last_mock_backend_status: MockFFEAgentlessBackendStatus | None = None

    def __init__(
        self,
        name: str,
        *,
        doc: str,
        weblog_env: dict[str, str | None] | None = None,
        other_weblog_containers: tuple[type[TestedContainer], ...] = (),
        scenario_groups: tuple[ScenarioGroup, ...] = (),
        use_proxy_for_weblog: bool = False,
    ) -> None:
        super().__init__(
            name,
            doc=doc,
            include_agent=False,
            library_interface_timeout=0,
            other_weblog_containers=other_weblog_containers,
            scenario_groups=[*scenario_groups, all_scenario_groups.agentless],
            use_proxy_for_agent=False,
            use_proxy_for_weblog=use_proxy_for_weblog,
            weblog_env=weblog_env,
        )

    def configure(self, config: pytest.Config) -> None:
        try:
            if self.replay:
                self._load_mock_backend_status()
            else:
                self._last_mock_backend_status = None
                self._start_mock_backend()

            super().configure(config)
        except BaseException:
            self._stop_mock_backend(persist_status=False)
            raise

    def _start_mock_backend(self) -> None:
        assert self._mock_backend is None, "mock FFE agentless backend is already running"

        self._mock_backend = MockFFEAgentlessBackendServer()
        self._mock_backend.reset()

        environment = self.weblog_infra.library_container.environment
        environment |= {
            "DD_API_KEY": EXPECTED_API_KEY,
            "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL": self._mock_backend.library_config_url,
        }
        self.weblog_infra.library_container.extra_hosts = extra_hosts_for_environment(environment)

    def mock_backend_status(self) -> MockFFEAgentlessBackendStatus | None:
        if self._mock_backend is not None:
            return self._mock_backend.status()
        return self._last_mock_backend_status

    @property
    def _mock_backend_status_path(self) -> Path:
        return Path(self.host_log_folder) / self._mock_backend_status_filename

    def _load_mock_backend_status(self) -> None:
        self._last_mock_backend_status = cast(
            "MockFFEAgentlessBackendStatus",
            json.loads(self._mock_backend_status_path.read_text(encoding="utf-8")),
        )

    def _stop_mock_backend(self, *, persist_status: bool = True) -> None:
        backend = self._mock_backend
        if backend is None:
            return

        self._mock_backend = None
        try:
            if persist_status:
                self._last_mock_backend_status = backend.status()
                self._mock_backend_status_path.parent.mkdir(parents=True, exist_ok=True)
                self._mock_backend_status_path.write_text(
                    json.dumps(self._last_mock_backend_status, indent=2) + "\n",
                    encoding="utf-8",
                )
        finally:
            backend.close()

    def close_targets(self) -> None:
        try:
            super().close_targets()
        finally:
            self._stop_mock_backend()


class FeatureFlaggingAgentlessEndToEndScenario(AgentlessEndToEndScenario):
    """FFE end-to-end scenario with UFC available before the weblog starts."""

    def __init__(
        self,
        name: str,
        *,
        doc: str = "Validate default agentless UFC delivery and evaluation without a Datadog Agent.",
        exposure_egress: Literal["sidecar", "direct"] | None = None,
        weblog_env: dict[str, str | None] | None = None,
    ) -> None:
        self.exposure_egress = exposure_egress
        self._expected_evp_capture_paths: set[str] = set()
        self._shutdown_evp_evaluation: DirectEVPShutdownEvaluation | None = None
        self._last_direct_evp_runtime_evidence: dict[str, Any] | None = None
        self._last_direct_evp_shutdown_evidence: dict[str, Any] | None = None
        environment: dict[str, str | None] = {
            # The shared weblogs use this switch to install their OpenFeature provider. The
            # configuration source selects how the provider receives flags; it does not make the
            # application adopt the provider on its own.
            "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
            "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE": "agentless",
            # Both variables are integer seconds across the SDKs: Java parses them with
            # getInteger, and the shared configuration registry declares them "int" with an
            # allowed pattern of [1-9]\d*. A fractional value only ever worked on Node, which
            # has a single numeric type and does not enforce that pattern; it is a hard parse
            # error in the strictly-typed libraries. 1s is the smallest legal interval.
            "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_POLL_INTERVAL_SECONDS": "1",
            "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_REQUEST_TIMEOUT_SECONDS": "2",
            "DD_REMOTE_CONFIGURATION_ENABLED": "false",
        }
        environment.update(weblog_env or {})

        other_weblog_containers: tuple[type[TestedContainer], ...] = ()
        if exposure_egress is not None:
            environment |= {
                # The reserved .invalid domain fails closed if a request bypasses the proxy.
                "DD_SITE": "mock-intake.invalid",
                "DD_PROXY_HTTPS": f"http://proxy:{ProxyPorts.datadog_direct}",
                "HTTPS_PROXY": f"http://proxy:{ProxyPorts.datadog_direct}",
            }

        if exposure_egress == "sidecar":
            serverless_init_port = str(ServerlessInitContainer.apm_receiver_port)
            environment |= {
                "DD_AGENT_HOST": "ffe-serverless-init",
                "DD_TRACE_AGENT_PORT": serverless_init_port,
                "DD_TRACE_AGENT_URL": f"http://ffe-serverless-init:{serverless_init_port}",
            }
            other_weblog_containers = (ServerlessInitContainer,)

        super().__init__(
            name,
            doc=doc,
            other_weblog_containers=other_weblog_containers,
            scenario_groups=(all_scenario_groups.ffe,),
            use_proxy_for_weblog=exposure_egress is not None,
            weblog_env=environment,
        )

        if exposure_egress == "direct":
            self.weblog_infra.library_container.environment[DIRECT_EVP_SHUTDOWN_FLUSH_ENV] = "true"
            self.weblog_infra.library_container.volumes[DIRECT_EVP_CA_BUNDLE_SOURCE] = {
                "bind": DIRECT_EVP_CA_BUNDLE_CONTAINER_PATH,
                "mode": "ro",
            }
            # Direct mode uses the proxy only to capture HTTPS intake requests.
            # Do not advertise the proxy as a local Agent endpoint.
            for env_name in DIRECT_EVP_AGENT_VARIABLES:
                self.weblog_infra.library_container.environment.pop(env_name, None)

    def configure(self, config: pytest.Config) -> None:
        try:
            super().configure(config)
            if self.exposure_egress is not None:
                interfaces.datadog_sidecar.configure(self.host_log_folder, replay=self.replay)
                interfaces.datadog_direct.configure(self.host_log_folder, replay=self.replay)
        except BaseException:
            self._stop_mock_backend(persist_status=False)
            raise

    @property
    def serverless_init_container(self) -> ServerlessInitContainer:
        for container in self.weblog_infra.get_containers():
            if isinstance(container, ServerlessInitContainer):
                return container
        raise ValueError("This scenario has no serverless-init container")

    def _set_containers_dependancies(self) -> None:
        super()._set_containers_dependancies()
        if self.exposure_egress == "sidecar":
            self.serverless_init_container.depends_on.append(self.proxy_container)

    def _start_interfaces_watchdog(self) -> None:
        super()._start_interfaces_watchdog()
        if self.exposure_egress is not None:
            self.start_interfaces_watchdog([interfaces.datadog_sidecar, interfaces.datadog_direct])

    def _wait_for_app_readiness(self) -> None:
        if self.exposure_egress is not None:
            return
        super()._wait_for_app_readiness()

    def _set_components(self) -> None:
        super()._set_components()
        if self.exposure_egress == "sidecar":
            self.components["serverless-init"] = self.serverless_init_container.serverless_init_version

    def register_expected_evp_capture(self, path: str) -> None:
        """Register a canonical signal path that must be captured before shutdown."""
        if self.exposure_egress is None:
            raise ValueError("EVP capture expectations require an egress scenario")
        if path not in DIRECT_EVP_SIGNAL_PATHS:
            raise ValueError(f"Unsupported Feature Flags EVP path {path!r}")
        self._expected_evp_capture_paths.add(path)

    def register_shutdown_evp_evaluation(
        self,
        *,
        signal_path: str,
        request_path: str,
        body: dict[str, Any],
        flag_key: str,
        subject_id: str,
    ) -> None:
        """Defer one evaluation to immediately before the bounded shutdown flush."""
        if self.exposure_egress != "direct":
            raise ValueError("Shutdown EVP evaluation requires the direct egress scenario")
        if signal_path not in DIRECT_EVP_SIGNAL_PATHS:
            raise ValueError(f"Unsupported Feature Flags EVP path {signal_path!r}")
        if self._shutdown_evp_evaluation is not None:
            raise ValueError("Only one shutdown EVP evaluation may be registered")
        self._shutdown_evp_evaluation = DirectEVPShutdownEvaluation(
            signal_path=signal_path,
            request_path=request_path,
            body=body,
            flag_key=flag_key,
            subject_id=subject_id,
        )

    @property
    def _direct_evp_runtime_evidence_path(self) -> Path:
        return Path(self.host_log_folder) / DIRECT_EVP_RUNTIME_EVIDENCE_FILENAME

    @property
    def _direct_evp_shutdown_evidence_path(self) -> Path:
        return Path(self.host_log_folder) / DIRECT_EVP_SHUTDOWN_EVIDENCE_FILENAME

    def direct_evp_runtime_evidence(self) -> dict[str, Any]:
        """Return preserved live-container evidence for a direct scenario run."""
        if self._last_direct_evp_runtime_evidence is None:
            raise AssertionError("Direct EVP runtime evidence was not captured")
        return self._last_direct_evp_runtime_evidence

    def direct_evp_shutdown_evidence(self) -> dict[str, Any]:
        """Return preserved shutdown-flush evidence for a direct scenario run."""
        if self._last_direct_evp_shutdown_evidence is None:
            raise AssertionError("Direct EVP shutdown evidence was not captured")
        return self._last_direct_evp_shutdown_evidence

    @staticmethod
    def _process_rows(container: Container) -> tuple[list[dict[str, str]], str | None]:
        try:
            process_table = container.top(ps_args="-eo pid,ppid,comm,args")
            titles = [str(title).lower() for title in process_table.get("Titles", [])]
            processes = [
                {title: str(value) for title, value in zip(titles, row, strict=True)}
                for row in process_table.get("Processes", [])
            ]
            return processes, None
        except BaseException as error:
            return [], f"{type(error).__name__}: {error}"

    @staticmethod
    def _pid1_command(container: Container) -> tuple[str, str | None]:
        try:
            result = container.exec_run(["sh", "-c", "tr '\\000' ' ' </proc/1/cmdline"])
            if result.exit_code != 0:
                return "", f"exec exit code {result.exit_code}"
            return result.output.decode("utf-8").strip(), None
        except BaseException as error:
            return "", f"{type(error).__name__}: {error}"

    def _capture_direct_evp_runtime_evidence(self) -> None:
        """Capture live Docker/network/process state without retaining credentials."""
        self._network.reload()
        network_members = self._network.attrs.get("Containers") or {}
        live_containers = get_docker_client().containers.list(
            all=False,
            filters={"network": self._network.id},
        )
        containers: list[dict[str, Any]] = []
        weblog_environment: dict[str, Any] | None = None

        for container in sorted(live_containers, key=lambda item: item.name):
            container.reload()
            attributes = container.attrs
            state = attributes.get("State", {})
            config = attributes.get("Config", {})
            labels = config.get("Labels") or {}
            environment = dict(
                item.split("=", 1) for item in config.get("Env", []) if isinstance(item, str) and "=" in item
            )
            processes, top_error = self._process_rows(container)
            pid1_command, pid1_error = self._pid1_command(container)
            containers.append(
                {
                    "id": container.id,
                    "name": container.name,
                    "image": config.get("Image"),
                    "image_id": attributes.get("Image"),
                    "library": labels.get("system-tests-library"),
                    "weblog_variant": labels.get("system-tests-weblog-variant"),
                    "status": container.status,
                    "running": state.get("Running"),
                    "state_pid": state.get("Pid"),
                    "pid1_command": pid1_command,
                    "pid1_error": pid1_error,
                    "processes": processes,
                    "top_error": top_error,
                    "networks": sorted(attributes.get("NetworkSettings", {}).get("Networks", {})),
                    "mounts": [
                        {
                            "destination": mount.get("Destination"),
                            "read_write": mount.get("RW"),
                            "source": mount.get("Source"),
                            "type": mount.get("Type"),
                        }
                        for mount in attributes.get("Mounts", [])
                    ],
                }
            )

            if container.name == self.weblog_infra.library_container.container_name:
                weblog_environment = {
                    "agent_variables_present": sorted(
                        name for name in DIRECT_EVP_AGENT_VARIABLES if name in environment
                    ),
                    "api_key_matches_expected": environment.get("DD_API_KEY") == EXPECTED_API_KEY,
                    "api_key_present": bool(environment.get("DD_API_KEY")),
                    "configuration_source": environment.get("DD_FEATURE_FLAGS_CONFIGURATION_SOURCE"),
                    "custom_configuration_url_present": bool(
                        environment.get("DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL")
                    ),
                    "provider_enabled": environment.get("DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED"),
                    "shutdown_flush_enabled": environment.get(DIRECT_EVP_SHUTDOWN_FLUSH_ENV),
                    "site": environment.get("DD_SITE"),
                    "tls_ca_bundle": environment.get("NODE_EXTRA_CA_CERTS")
                    or environment.get("SSL_CERT_FILE")
                    or environment.get("REQUESTS_CA_BUNDLE"),
                }

        self._last_direct_evp_runtime_evidence = {
            "captured_at": datetime.now(UTC).isoformat(),
            "containers": containers,
            "network": {
                "id": self._network.id,
                "name": self._network.name,
                "container_ids": sorted(network_members),
                "container_names": sorted(
                    member.get("Name") for member in network_members.values() if isinstance(member.get("Name"), str)
                ),
            },
            "weblog_environment": weblog_environment,
        }
        self._direct_evp_runtime_evidence_path.write_text(
            json.dumps(self._last_direct_evp_runtime_evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _capture_has_shutdown_evaluation(data: dict[str, Any], evaluation: DirectEVPShutdownEvaluation) -> bool:
        if data.get("path") != evaluation.signal_path:
            return False
        content = data.get("request", {}).get("content")
        if not isinstance(content, dict):
            return False
        events = content.get("exposures")
        if not isinstance(events, list):
            events = content.get("flagEvaluations")
        if not isinstance(events, list):
            return False
        return any(
            isinstance(event, dict)
            and isinstance(event.get("flag"), dict)
            and event["flag"].get("key") == evaluation.flag_key
            and isinstance(event.get("subject"), dict)
            and event["subject"].get("id") == evaluation.subject_id
            for event in events
        )

    @staticmethod
    def _stopped_container_state(container: Container) -> dict[str, Any]:
        try:
            container.reload()
            state = container.attrs.get("State", {})
            return {
                "error": state.get("Error"),
                "exit_code": state.get("ExitCode"),
                "finished_at": state.get("FinishedAt"),
                "oom_killed": state.get("OOMKilled"),
                "running": state.get("Running"),
                "status": container.status,
            }
        except BaseException as error:
            return {"inspection_error": f"{type(error).__name__}: {error}"}

    @staticmethod
    def _shutdown_markers(container: Container) -> tuple[list[dict[str, str]], list[str]]:
        """Read structured shutdown lifecycle markers from the stopped container's logs."""
        markers: list[dict[str, str]] = []
        errors: list[str] = []
        for stream, options in (
            ("stdout", {"stdout": True, "stderr": False}),
            ("stderr", {"stdout": False, "stderr": True}),
        ):
            try:
                output = container.logs(**options)
                text = output.decode("utf-8") if isinstance(output, bytes) else str(output)
            except BaseException as error:
                errors.append(f"{stream}: {type(error).__name__}: {error}")
                continue

            for line in text.splitlines():
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(value, dict) or value.get("event") != DIRECT_EVP_SHUTDOWN_MARKER_EVENT:
                    continue
                markers.append(
                    {
                        "event": str(value.get("event")),
                        "stream": stream,
                        "timestamp": str(value.get("timestamp")),
                    }
                )
        return markers, errors

    def _stop_weblog(self, *, is_empty_test_run: bool) -> None:
        if self.exposure_egress != "direct" or self.replay or is_empty_test_run:
            super()._stop_weblog(is_empty_test_run=is_empty_test_run)
            return

        self._capture_direct_evp_runtime_evidence()
        evaluation = self._shutdown_evp_evaluation
        if evaluation is None:
            super()._stop_weblog(is_empty_test_run=is_empty_test_run)
            return

        interface = interfaces.datadog_direct

        def matcher(data: dict[str, Any]) -> bool:
            return self._capture_has_shutdown_evaluation(data, evaluation)

        # Timer-based writers may flush the first event after a long idle period immediately.
        # Complete one unique exposure first so the target below is produced inside a fresh flush
        # window. The priming event is evidence, not the event under test; the target must still
        # start its request only after the runtime's truthful server-close marker.
        priming_subject_id = f"{evaluation.subject_id}-flush-window-prime"
        priming_body = dict(evaluation.body)
        priming_body["targetingKey"] = priming_subject_id
        priming_evaluation = DirectEVPShutdownEvaluation(
            signal_path=evaluation.signal_path,
            request_path=evaluation.request_path,
            body=priming_body,
            flag_key=evaluation.flag_key,
            subject_id=priming_subject_id,
        )

        def priming_matcher(data: dict[str, Any]) -> bool:
            return self._capture_has_shutdown_evaluation(data, priming_evaluation)

        priming_started_at = datetime.now(UTC)
        priming_response = weblog.post(priming_evaluation.request_path, json=priming_evaluation.body)
        priming_finished_at = datetime.now(UTC)
        priming_observed = interface.wait_for(priming_matcher, timeout=DIRECT_EVP_CAPTURE_WAIT_SECONDS)
        priming_captures = list(filter(priming_matcher, interface.get_data()))
        if not priming_observed or len(priming_captures) != 1:
            raise RuntimeError(
                "Could not establish one completed direct-EVP flush immediately before the shutdown target"
            )

        matching_before = list(filter(matcher, interface.get_data()))
        evaluation_started_at = datetime.now(UTC)
        response = weblog.post(evaluation.request_path, json=evaluation.body)
        evaluation_finished_at = datetime.now(UTC)
        matching_before_stop = list(filter(matcher, interface.get_data()))

        runtime_container = self.weblog_infra.library_container.runtime_container
        stop_started_at = datetime.now(UTC)
        stop_started = time.monotonic()
        stop_error: BaseException | None = None
        try:
            # Do not call the weblog's explicit /flush endpoint here. The event must remain
            # buffered until Docker sends SIGTERM and the language runtime runs its shutdown
            # lifecycle.
            self.weblog_infra.stop(flush=False, stop_timeout=DIRECT_EVP_STOP_TIMEOUT_SECONDS)
        except BaseException as error:
            stop_error = error
        stop_duration = time.monotonic() - stop_started
        stopped_at = datetime.now(UTC)
        stopped_state = self._stopped_container_state(runtime_container)
        shutdown_markers, shutdown_marker_errors = self._shutdown_markers(runtime_container)

        capture_observed = interface.wait_for(matcher, timeout=DIRECT_EVP_CAPTURE_WAIT_SECONDS)
        interface.wait(DIRECT_EVP_CAPTURE_SETTLE_SECONDS)
        matching_after = list(filter(matcher, interface.get_data()))
        self._last_direct_evp_shutdown_evidence = {
            "capture_files": [capture.get("log_filename") for capture in matching_after],
            "capture_observed_after_stop": capture_observed,
            "capture_request_started_at": [
                capture.get("request", {}).get("timestamp_start") for capture in matching_after
            ],
            "captures_after_settle": len(matching_after),
            "captures_before_evaluation": len(matching_before),
            "captures_before_stop": len(matching_before_stop),
            "evaluation_finished_at": evaluation_finished_at.isoformat(),
            "evaluation_started_at": evaluation_started_at.isoformat(),
            "evaluation_status_code": response.status_code,
            "explicit_flush": False,
            "flag_key": evaluation.flag_key,
            "flush_window_primed": True,
            "priming_capture_files": [capture.get("log_filename") for capture in priming_captures],
            "priming_capture_request_started_at": [
                capture.get("request", {}).get("timestamp_start") for capture in priming_captures
            ],
            "priming_evaluation_finished_at": priming_finished_at.isoformat(),
            "priming_evaluation_started_at": priming_started_at.isoformat(),
            "priming_evaluation_status_code": priming_response.status_code,
            "priming_subject_id": priming_subject_id,
            "shutdown_bound_seconds": DIRECT_EVP_SHUTDOWN_BOUND_SECONDS,
            "shutdown_duration_seconds": stop_duration,
            "shutdown_marker_errors": shutdown_marker_errors,
            "shutdown_markers": shutdown_markers,
            "signal_path": evaluation.signal_path,
            "stop_error": None if stop_error is None else f"{type(stop_error).__name__}: {stop_error}",
            "stop_started_at": stop_started_at.isoformat(),
            "stop_timeout_seconds": DIRECT_EVP_STOP_TIMEOUT_SECONDS,
            "stopped_at": stopped_at.isoformat(),
            "stopped_container": stopped_state,
            "subject_id": evaluation.subject_id,
        }
        self._direct_evp_shutdown_evidence_path.write_text(
            json.dumps(self._last_direct_evp_shutdown_evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if stop_error is not None:
            raise stop_error

    def _wait_for_expected_evp_captures(self, *, is_empty_test_run: bool) -> None:
        """Keep the application alive until selected async EVP writers are observable."""
        if self.replay or self.exposure_egress is None or is_empty_test_run:
            return
        if not self._expected_evp_capture_paths and self._shutdown_evp_evaluation is None:
            raise RuntimeError("A non-empty Feature Flags EVP run registered no expected capture paths")

        interface = interfaces.datadog_sidecar if self.exposure_egress == "sidecar" else interfaces.datadog_direct
        missing_paths: list[str] = []
        for path in sorted(self._expected_evp_capture_paths):

            def captured(data: dict[str, Any], expected_path: str = path) -> bool:
                return data.get("path") == expected_path

            logger.terminal.write_sep("-", f"Wait for {path} on {interface} before stopping the weblog")
            logger.terminal.flush()
            if not interface.wait_for(captured, timeout=DIRECT_EVP_CAPTURE_WAIT_SECONDS):
                missing_paths.append(path)

        if missing_paths:
            raise RuntimeError(f"Timed out waiting for Feature Flags EVP captures: {', '.join(missing_paths)}")

        # Preserve a bounded window in which an unsafe retry would appear as a duplicate capture.
        interface.wait(DIRECT_EVP_CAPTURE_SETTLE_SECONDS)

    def _wait_and_stop_containers(self, *, is_empty_test_run: bool) -> None:
        try:
            self._wait_for_expected_evp_captures(is_empty_test_run=is_empty_test_run)
        finally:
            if self.replay and self.exposure_egress == "direct":
                self._last_direct_evp_runtime_evidence = json.loads(
                    self._direct_evp_runtime_evidence_path.read_text(encoding="utf-8")
                )
                if self._direct_evp_shutdown_evidence_path.exists():
                    self._last_direct_evp_shutdown_evidence = json.loads(
                        self._direct_evp_shutdown_evidence_path.read_text(encoding="utf-8")
                    )
            super()._wait_and_stop_containers(is_empty_test_run=is_empty_test_run)
            if self.exposure_egress is not None:
                if self.replay:
                    self._load_telemetry_interfaces()
                elif self.exposure_egress == "sidecar":
                    self.serverless_init_container.stop()

                interfaces.datadog_sidecar.check_deserialization_errors()
                interfaces.datadog_direct.check_deserialization_errors()

    @staticmethod
    def _load_telemetry_interfaces() -> None:
        telemetry_interfaces: tuple[ProxyBasedInterfaceValidator, ...] = (
            interfaces.datadog_sidecar,
            interfaces.datadog_direct,
        )
        for interface in telemetry_interfaces:
            interface.load_data_from_logs()
