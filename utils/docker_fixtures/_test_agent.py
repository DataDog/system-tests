import base64
from collections.abc import Generator
import contextlib
import datetime
import hashlib
from http import HTTPStatus
import json
from pathlib import Path
import os
import time
from typing import TypedDict, Any
import urllib.parse

import pytest
import requests
from retry import retry

from utils._logger import logger
from utils.dd_constants import RemoteConfigApplyState, Capabilities
from utils.parametric.spec import remoteconfig
from utils.parametric.spec.trace import V06StatsPayload
from utils.parametric.spec.trace import decode_v06_stats
from utils.parametric.spec.trace import Trace

from ._core import get_host_port, get_docker_client, docker_run


def _request_token(request: pytest.FixtureRequest) -> str:
    token = ""
    token += request.module.__name__
    token += f".{request.cls.__name__}" if request.cls else ""
    token += f".{request.node.name}"
    return token


class AgentRequest(TypedDict):
    method: str
    url: str
    headers: dict[str, str]
    body: str


class AgentRequestV06Stats(AgentRequest):
    body: V06StatsPayload  # type: ignore[misc]


class TestAgentFactory:
    """Handle everything to create the TestAgentApi"""

    image = "ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:v1.32.0"

    def __init__(self, host_log_folder: str):
        self.host_log_folder = host_log_folder

    @retry(delay=10, tries=3)
    def pull(self) -> None:
        if len(get_docker_client().images.list(name=self.image)) == 0:
            logger.stdout(f"Pull test agent image {self.image}...")
            get_docker_client().images.pull(self.image)

    @contextlib.contextmanager
    def get_test_agent_api(
        self,
        request: pytest.FixtureRequest,
        worker_id: str,
        container_name: str,
        docker_network: str,
        container_otlp_http_port: int,
        container_otlp_grpc_port: int,
    ) -> Generator["TestAgentAPI", None, None]:
        # (meta_tracer_version_header) Not all clients (go for example) submit the tracer version
        # (trace_content_length) go client doesn't submit content length header
        env = {
            "ENABLED_CHECKS": "trace_count_header",
            "OTLP_HTTP_PORT": str(container_otlp_http_port),
            "OTLP_GRPC_PORT": str(container_otlp_grpc_port),
        }
        if os.getenv("DEV_MODE") is not None:
            env["SNAPSHOT_CI"] = "0"

        host_port = get_host_port(worker_id, 4600)
        container_port = 8126
        otlp_http_host_port = get_host_port(worker_id, 4701)
        otlp_grpc_host_port = get_host_port(worker_id, 4802)

        log_path = f"{self.host_log_folder}/outputs/{request.cls.__name__}/{request.node.name}/agent_log.log"
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)

        with (
            open(log_path, "w+", encoding="utf-8") as log_file,
            docker_run(
                image=self.image,
                name=container_name,
                env=env,
                volumes={"./snapshots": "/snapshots"},
                ports={
                    f"{container_port}/tcp": host_port,
                    f"{container_otlp_http_port}/tcp": otlp_http_host_port,
                    f"{container_otlp_grpc_port}/tcp": otlp_grpc_host_port,
                },
                log_file=log_file,
                network=docker_network,
            ),
        ):
            client = TestAgentAPI(
                container_name,
                container_port,
                self.host_log_folder,
                pytest_request=request,
                otlp_http_host_port=otlp_http_host_port,
                host_port=host_port,
                network=docker_network,
            )
            time.sleep(0.2)  # initial wait time, the trace agent takes 200ms to start
            for _ in range(100):
                try:
                    resp = client.info()
                except Exception as e:
                    logger.debug(f"Wait for 0.1s for the test agent to be ready {e}")
                    time.sleep(0.1)
                else:
                    if resp["version"] != "test":
                        message = f"""Agent version {resp["version"]} is running instead of the test agent.
                        Stop the agent on port {container_port} and try again."""
                        pytest.fail(message, pytrace=False)

                    logger.info("Test agent is ready")
                    break
            else:
                logger.error("Could not connect to test agent")
                pytest.fail(f"Could not connect to test agent, check the log file {log_file.name}.", pytrace=False)

            # If the snapshot mark is on the test case then do a snapshot test
            marks = list(request.node.iter_markers(name="snapshot"))
            assert len(marks) <= 1, "Multiple snapshot marks detected"
            if marks:
                snap = marks[0]
                assert len(snap.args) == 0, "only keyword arguments are supported by the snapshot decorator"
                if "token" not in snap.kwargs:
                    snap.kwargs["token"] = _request_token(request).replace(" ", "_").replace(os.path.sep, "_")
                with client.snapshot_context(**snap.kwargs):
                    yield client
            else:
                yield client

        request.node.add_report_section("teardown", "Test Agent Output", f"Log file:\n./{log_path}")


class TestAgentAPI:
    __test__ = False  # pytest must not collect it

    def __init__(
        self,
        container_name: str,
        container_port: int,
        host_log_folder: str,
        host_port: int,
        otlp_http_host_port: int,
        pytest_request: pytest.FixtureRequest,
        network: str,
    ):
        self.container_name = container_name
        self.container_port = container_port
        self.network = network

        self.host = "localhost"
        self.host_port = host_port
        self.otlp_http_host_port = otlp_http_host_port

        self._session = requests.Session()
        self._pytest_request = pytest_request
        self.log_path = (
            f"{host_log_folder}/outputs/{pytest_request.cls.__name__}/{pytest_request.node.name}/agent_api.log"
        )
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)

    def _url(self, path: str) -> str:
        return urllib.parse.urljoin(f"http://{self.host}:{self.host_port}", path)

    def _otlp_url(self, path: str) -> str:
        return urllib.parse.urljoin(f"http://{self.host}:{self.otlp_http_host_port}", path)

    def _write_log(self, log_type: str, json_trace: Any):  # noqa: ANN401
        with open(self.log_path, "a") as log:
            log.write(f"\n{log_type}>>>>\n")
            log.write(json.dumps(json_trace))

    def traces(self, *, clear: bool = False, **kwargs: Any) -> list[Trace]:  # noqa: ANN401
        resp = self._session.get(self._url("/test/session/traces"), **kwargs)
        if clear:
            self.clear()
        resp_json = resp.json()
        self._write_log("traces", resp_json)
        return resp_json

    def metrics(self, *, clear: bool = False, **kwargs: Any) -> list[Any]:  # noqa: ANN401
        resp = self._session.get(self._otlp_url("/test/session/metrics"), **kwargs)
        if clear:
            self.clear()
        resp_json: list = resp.json()
        self._write_log("metrics", resp_json)
        return resp_json

    def set_remote_config(self, path: str, payload: dict):
        resp = self._session.post(self._url("/test/session/responses/config/path"), json={"path": path, "msg": payload})
        assert resp.status_code == HTTPStatus.ACCEPTED

    def get_remote_config(self):
        resp = self._session.get(self._url("/v0.7/config"))
        resp_json = resp.json()
        result = []
        if resp_json and resp_json["target_files"]:
            target_files = resp_json["target_files"]
            for target in target_files:
                path = target["path"]
                msg = json.loads(str(base64.b64decode(target["raw"]), encoding="utf-8"))
                result.append({"path": path, "msg": msg})
        return result

    def add_remote_config(self, path: str, payload: dict):
        current_rc = self.get_remote_config()
        current_rc.append({"path": path, "msg": payload})
        remote_config_payload = self._build_config_path_response(current_rc)
        resp = self._session.post(self._url("/test/session/responses/config"), remote_config_payload)
        assert resp.status_code == HTTPStatus.ACCEPTED

    @staticmethod
    def _build_config_path_response(config: list) -> str:
        expires_date = datetime.datetime.strftime(
            datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(days=1), "%Y-%m-%dT%H:%M:%SZ"
        )
        roots = [
            str(
                base64.b64encode(
                    bytes(
                        json.dumps(
                            {
                                "signatures": [],
                                "signed": {
                                    "_type": "root",
                                    "consistent_snapshot": True,
                                    "expires": "1986-12-11T00:00:00Z",
                                    "keys": {},
                                    "roles": {},
                                    "spec_version": "1.0",
                                    "version": 2,
                                },
                            }
                        ),
                        encoding="utf-8",
                    )
                ),
                encoding="utf-8",
            )
        ]

        client_configs = []
        target_files = []
        targets_tmp = {}
        for item in config:
            client_configs.append(item["path"])
            item["msg_enc"] = bytes(json.dumps(item["msg"]), encoding="utf-8")
            tf = {
                "path": item["path"],
                "raw": str(base64.b64encode(item["msg_enc"]), encoding="utf-8"),
            }
            target_files.append(tf)
            targets_tmp[item["path"]] = {
                "custom": {"c": [""], "v": 0},
                "hashes": {"sha256": hashlib.sha256(item["msg_enc"]).hexdigest()},
                "length": len(item["msg_enc"]),
            }

        data = {
            "signatures": [{"keyid": "", "sig": ""}],
            "signed": {
                "_type": "targets",
                "custom": {"opaque_backend_state": ""},
                "expires": expires_date,
                "spec_version": "1.0.0",
                "targets": targets_tmp,
            },
            "version": 0,
        }
        targets = str(base64.b64encode(bytes(json.dumps(data), encoding="utf-8")), encoding="utf-8")
        remote_config_payload = {
            "roots": roots,
            "targets": targets,
            "target_files": target_files,
            "client_configs": client_configs,
        }
        return json.dumps(remote_config_payload)

    def set_trace_delay(self, delay: int):
        resp = self._session.post(self._url("/test/settings"), json={"trace_request_delay": delay})
        assert resp.status_code == HTTPStatus.ACCEPTED

    def raw_telemetry(self, *, clear: bool = False):
        raw_reqs = self.requests()
        reqs = []
        for req in raw_reqs:
            if req["url"].endswith("/telemetry/proxy/api/v2/apmtelemetry"):
                reqs.append(req)
        if clear:
            self.clear()
        return reqs

    def telemetry(self, *, clear: bool = False):
        resp = self._session.get(self._url("/test/session/apmtelemetry"))
        if clear:
            self.clear()
        return resp.json()

    # def tracestats(self, **kwargs: Any):
    #     resp = self._session.get(self._url("/test/session/stats"), **kwargs)
    #     resp_json = resp.json()
    #     self._write_log("tracestats", resp_json)
    #     return resp_json

    def requests(self) -> list[AgentRequest]:
        resp = self._session.get(self._url("/test/session/requests"))
        resp_json = resp.json()
        self._write_log("requests", resp_json)
        return resp_json

    def rc_requests(self, *, post_only: bool = False):
        reqs = self.requests()
        rc_reqs = [r for r in reqs if r["url"].endswith("/v0.7/config") and (not post_only or r["method"] == "POST")]
        for r in rc_reqs:
            r["body"] = json.loads(base64.b64decode(r["body"]).decode("utf-8"))
        return rc_reqs

    def get_tracer_flares(self):
        resp = self._session.get(self._url("/test/session/tracerflares"))
        resp_json = resp.json()
        self._write_log("tracerflares", resp_json)
        return resp_json

    def get_v06_stats_requests(self) -> list[AgentRequestV06Stats]:
        raw_requests = [r for r in self.requests() if "/v0.6/stats" in r["url"]]

        agent_requests = []
        for raw in raw_requests:
            agent_requests.append(
                AgentRequestV06Stats(
                    method=raw["method"],
                    url=raw["url"],
                    headers=raw["headers"],
                    body=decode_v06_stats(base64.b64decode(raw["body"])),
                )
            )
        return agent_requests

    def clear(self) -> None:
        self._session.get(self._url("/test/session/clear"))
        self._session.get(self._otlp_url("/test/session/clear"))

    def info(self):
        resp = self._session.get(self._url("/info"))

        if resp.status_code != HTTPStatus.OK:
            message = f"Test agent unexpected {resp.status_code} response: {resp.text}"
            logger.error(message)
            raise ValueError(message)

        resp_json = resp.json()
        self._write_log("info", resp_json)
        return resp_json

    @contextlib.contextmanager
    def snapshot_context(self, token: str, ignores: list[str] | None = None):
        ignores = ignores or []
        try:
            resp = self._session.get(self._url(f"/test/session/start?test_session_token={token}"))
            resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Could not connect to test agent: {e}") from e
        else:
            yield self
            # Query for the results of the test.
            resp = self._session.get(
                self._url(f"/test/session/snapshot?ignores={','.join(ignores)}&test_session_token={token}")
            )
            if resp.status_code != HTTPStatus.OK:
                raise RuntimeError(resp.text)

    def wait_for_num_traces(
        self, num: int, *, clear: bool = False, wait_loops: int = 30, sort_by_start: bool = True
    ) -> list[Trace]:
        """Wait for `num` traces to be received from the test agent.

        Returns after the number of traces has been received or raises otherwise after 2 seconds of polling.

        When sort_by_start=True returned traces are sorted by the span start time to simplify assertions by knowing that
        returned traces are in the same order as they have been created.
        """
        num_received = None
        traces = []
        for _ in range(wait_loops):
            try:
                traces = self.traces(clear=False)
            except requests.exceptions.RequestException:
                pass
            else:
                num_received = len(traces)
                if num_received == num:
                    if clear:
                        self.clear()
                    if sort_by_start:
                        for trace in traces:
                            # The testagent may receive spans and trace chunks in any order,
                            # so we sort the spans by start time if needed
                            trace.sort(key=lambda x: x["start"])
                        return sorted(traces, key=lambda t: t[0]["start"])
                    return traces
            time.sleep(0.1)
        raise ValueError(f"Number ({num}) of traces not available from test agent, got {num_received}:\n{traces}")

    def wait_for_num_spans(
        self, num: int, *, clear: bool = False, wait_loops: int = 30, sort_by_start: bool = True
    ) -> list[Trace]:
        """Wait for `num` spans to be received from the test agent.

        Returns after the number of spans has been received or raises otherwise after 2 seconds of polling.

        When sort_by_start=True returned traces are sorted by the span start time to simplify assertions by knowing that
        returned traces are in the same order as they have been created.
        """
        num_received = None
        for _ in range(wait_loops):
            try:
                traces = self.traces(clear=False)
            except requests.exceptions.RequestException:
                pass
            else:
                num_received = 0
                for trace in traces:
                    num_received += len(trace)
                if num_received == num:
                    if clear:
                        self.clear()

                    if sort_by_start:
                        for trace in traces:
                            # The testagent may receive spans and trace chunks in any order,
                            # so we sort the spans by start time if needed
                            trace.sort(key=lambda x: x["start"])
                        return sorted(traces, key=lambda t: t[0]["start"])
                    return traces
            time.sleep(0.1)
        raise ValueError(f"Number ({num}) of spans not available from test agent, got {num_received}")

    def wait_for_num_otlp_metrics(self, num: int, *, wait_loops: int = 30) -> list[Any]:
        """Wait for `num` metrics to be received from the test agent."""
        metrics = []
        for _ in range(wait_loops):
            try:
                metrics = self.metrics()
            except requests.exceptions.RequestException:
                pass
            else:
                if len(metrics) >= num:
                    return metrics
            time.sleep(0.1)
        raise ValueError(f"Number ({num}) of metrics not available from test agent, got {len(metrics)}")

    def wait_for_telemetry_event(self, event_name: str, *, clear: bool = False, wait_loops: int = 200):
        """Wait for and return the given telemetry event from the test agent."""
        for _ in range(wait_loops):
            try:
                events = self.telemetry(clear=False)
            except requests.exceptions.RequestException:
                pass
            else:
                for event in events:
                    e = self._get_telemetry_event(event, event_name)
                    if e:
                        if clear:
                            self.clear()
                        return e
            time.sleep(0.01)
        raise AssertionError(f"Telemetry event {event_name} not found")

    def wait_for_telemetry_configurations(
        self, *, service: str | None = None, clear: bool = False
    ) -> dict[str, list[dict]]:
        """Waits for and returns configurations captured in telemetry events.

        Telemetry events can be found in `app-started` or `app-client-configuration-change` events.
        The function ensures that at least one telemetry event is captured before processing.
        Returns a dictionary where keys are configuration names and values are lists of
        configuration dictionaries, allowing for multiple entries per configuration name
        with different origins.
        """
        events = []
        configurations: dict[str, list[dict]] = {}
        # Allow time for telemetry events to be captured
        time.sleep(1)
        # Attempt to retrieve telemetry events, suppressing request-related exceptions
        with contextlib.suppress(requests.exceptions.RequestException):
            events = self.telemetry(clear=False)
        if not events:
            raise AssertionError("No telemetry events were found. Ensure the application is sending telemetry events.")

        # Sort events by tracer_time to ensure configurations are processed in order
        events.sort(key=lambda r: r["tracer_time"])

        # Extract configuration data from relevant telemetry events
        for event in events:
            if service is not None and event["application"]["service_name"] != service:
                continue
            for event_type in ["app-started", "app-client-configuration-change"]:
                telemetry_event = self._get_telemetry_event(event, event_type)
                if telemetry_event:
                    for config in telemetry_event.get("payload", {}).get("configuration", []):
                        # Store all configurations, allowing multiple entries per name with different origins
                        config_name = config["name"]
                        if config_name not in configurations:
                            configurations[config_name] = []
                        configurations[config_name].append(config)
        if len(configurations) != 0:
            # Checking if we need to sort due to multiple sources being sent for the same config
            sample_key = next(iter(configurations))
            if "seq_id" in configurations[sample_key][0]:
                # Sort seq_id for each config from highest to lowest
                for payload in configurations.values():
                    payload.sort(key=lambda item: item["seq_id"], reverse=True)
        if clear:
            self.clear()
        return configurations

    def get_telemetry_config_by_origin(
        self,
        configurations: dict[str, list[dict]],
        config_name: str,
        origin: str,
        *,
        fallback_to_first: bool = False,
        return_value_only: bool = False,
    ) -> dict | str | int | bool | None:
        """Get a telemetry configuration by name and origin.

        Args:
            configurations: The dict returned by wait_for_telemetry_configurations()
            config_name: The configuration name to look for
            origin: The origin to look for (e.g., "default", "env_var", "fleet_stable_config")
            fallback_to_first: If True, return the first config if no config with the specified origin is found
            return_value_only: If True, return only the "value" field, otherwise return the full config dict

        Returns:
            The configuration dict, the value, or None depending on parameters

        """
        config_list = configurations.get(config_name, [])
        if not config_list:
            return None

        # Try to find config with the specified origin
        config = next((cfg for cfg in config_list if cfg.get("origin") == origin), None)

        # Fallback to first config if requested and no origin match found
        if config is None and fallback_to_first and config_list:
            config = config_list[0]

        if config is None:
            return None

        return config.get("value") if return_value_only else config

    def wait_for_telemetry_metrics(self, metric_name: str | None = None, *, clear: bool = False, wait_loops: int = 100):
        """Get the telemetry metrics from the test agent."""
        metrics = []

        for _ in range(wait_loops):
            for event in self.telemetry(clear=False):
                telemetry_event = self._get_telemetry_event(event, "generate-metrics")
                logger.debug("Found telemetry event: %s", telemetry_event)
                if telemetry_event is None:
                    continue
                for series in telemetry_event["payload"]["series"]:
                    if metric_name is None or series["metric"] == metric_name:
                        metrics.append(series)
                        break
            metrics.sort(key=lambda x: (x["metric"], x["tags"]))
            time.sleep(0.01)

        if clear:
            self.clear()
        return metrics

    def _get_telemetry_event(self, event: dict, request_type: str):
        """Extracts telemetry events from a message batch or returns the telemetry event if it
        matches the expected request_type and was not emitted from a sidecar.
        """
        if not event:
            return None
        if event["request_type"] == "message-batch":
            for message in event["payload"]:
                if message["request_type"] == request_type:
                    if message.get("application", {}).get("language_version") != "SIDECAR":
                        return message
        elif event["request_type"] == request_type:
            if event.get("application", {}).get("language_version") != "SIDECAR":
                return event
        return None

    def wait_for_rc_apply_state(
        self,
        product: str,
        state: RemoteConfigApplyState,
        *,
        clear: bool = False,
        wait_loops: int = 100,
        post_only: bool = False,
    ):
        """Wait for the given RemoteConfig apply state to be received by the test agent."""
        logger.info(f"Wait for RemoteConfig apply state {state} for product {product}")
        rc_reqs = []
        last_known_state = None
        for _ in range(wait_loops):
            try:
                rc_reqs = self.rc_requests(post_only=post_only)
            except requests.exceptions.RequestException:
                logger.exception("Error getting RC requests")
            else:
                # Look for the given apply state in the requests.
                logger.debug(f"Check {len(rc_reqs)} RC requests")
                for req in rc_reqs:
                    if req["body"]["client"]["state"].get("config_states") is None:
                        logger.debug("No config_states in request")
                        continue

                    for cfg_state in req["body"]["client"]["state"]["config_states"]:
                        if cfg_state["product"] != product:
                            logger.debug(f"Product {cfg_state['product']} does not match {product}")
                        elif cfg_state["apply_state"] != state.value:
                            if last_known_state != cfg_state["apply_state"]:
                                # this condition prevent to spam logs, because the last known state
                                # will probably be the same as the current state
                                last_known_state = cfg_state["apply_state"]
                                logger.debug(f"Apply state {cfg_state['apply_state']} does not match {state}")
                        else:
                            logger.info(f"Found apply state {state} for product {product}")
                            if clear:
                                self.clear()
                            return cfg_state
            time.sleep(0.01)
        raise AssertionError(f"No RemoteConfig apply status found, got requests {rc_reqs}")

    def wait_for_rc_capabilities(self, wait_loops: int = 100) -> set[Capabilities]:
        """Wait for the given RemoteConfig apply state to be received by the test agent."""
        for _ in range(wait_loops):
            try:
                rc_reqs = self.rc_requests()
            except requests.exceptions.RequestException:
                pass
            else:
                # Look for capabilities in the requests.
                for req in rc_reqs:
                    raw_caps = req["body"]["client"].get("capabilities")
                    if raw_caps:
                        # Capabilities can be a base64 encoded string or an array of numbers. This is due
                        # to the Go json library used in the trace agent accepting and being able to decode
                        # both: https://go.dev/play/p/fkT5Q7GE5VD

                        # byte-array:
                        if isinstance(raw_caps, list):
                            decoded_capabilities = bytes(raw_caps)
                        # base64-encoded string:
                        else:
                            decoded_capabilities = base64.b64decode(raw_caps)

                        int_capabilities = int.from_bytes(decoded_capabilities, byteorder="big")

                        if int_capabilities >= (1 << 64):
                            raise AssertionError(
                                f"RemoteConfig capabilities should only use 64 bits, {int_capabilities}"
                            )

                        valid_bits = sum(1 << c for c in Capabilities)
                        if int_capabilities & ~valid_bits != 0:
                            raise AssertionError(
                                f"RC capabilities contains unknown bits: {bin(int_capabilities & ~valid_bits)}"
                            )

                        capabilities_seen = remoteconfig.human_readable_capabilities(int_capabilities)
                        if len(capabilities_seen) > 0:
                            return capabilities_seen
            time.sleep(0.01)
        raise AssertionError("RemoteConfig capabilities were empty")

    def assert_rc_capabilities(self, expected_capabilities: set[Capabilities], wait_loops: int = 100) -> None:
        """Wait for the given RemoteConfig apply state to be received by the test agent."""
        seen_capabilities = self.wait_for_rc_capabilities(wait_loops)
        missing_capabilities = expected_capabilities.difference(seen_capabilities)
        if missing_capabilities:
            raise AssertionError(f"RemoteConfig capabilities missing: {missing_capabilities}")

    def wait_for_tracer_flare(self, case_id: str | None = None, *, clear: bool = False, wait_loops: int = 100):
        """Wait for the tracer-flare to be received by the test agent."""
        for _ in range(wait_loops):
            try:
                tracer_flares = self.get_tracer_flares()
            except requests.exceptions.RequestException:
                pass
            else:
                # Look for the given case_id in the tracer-flares.
                for tracer_flare in tracer_flares:
                    if case_id is None or tracer_flare["case_id"] == case_id:
                        if clear:
                            self.clear()
                        return tracer_flare
            time.sleep(0.01)
        raise AssertionError("No tracer-flare received")

    def logs(self) -> list[Any]:
        url = self._otlp_url("/test/session/logs")
        resp = self._session.get(url)
        result: list = resp.json()
        return result

    def wait_for_num_log_payloads(self, num: int, wait_loops: int = 30) -> list[Any]:
        """Wait for `num` logs to be received from the test agent."""
        for _ in range(wait_loops):
            logs = self.logs()
            if len(logs) >= num:
                return logs
            time.sleep(0.1)
        raise ValueError(f"Number {num} of logs not available from test agent, got {len(logs)}")
