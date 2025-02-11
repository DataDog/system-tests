import base64
from collections.abc import Iterable
import contextlib
import dataclasses
import os
import shutil
import json
import subprocess
import time
import datetime
import hashlib
from typing import Generator, TextIO, TypedDict
import urllib.parse

import requests  # type: ignore
import pytest

from utils.parametric.spec import remoteconfig
from utils.parametric.spec.trace import V06StatsPayload
from utils.parametric.spec.trace import Trace
from utils.parametric.spec.trace import decode_v06_stats
from utils.parametric._library_client import APMLibrary, APMLibraryClient

from utils import context, scenarios
from utils.dd_constants import RemoteConfigApplyState
from utils.tools import logger

from utils._context._scenarios.parametric import APMLibraryTestServer

# Max timeout in seconds to keep a container running
default_subprocess_run_timeout = 300


@pytest.fixture
def test_id(request) -> str:
    import uuid

    result = str(uuid.uuid4())[0:6]
    logger.info(f"Test {request.node.nodeid} ID: {result}")
    return result


class AgentRequest(TypedDict):
    method: str
    url: str
    headers: dict[str, str]
    body: str


class AgentRequestV06Stats(AgentRequest):
    body: V06StatsPayload  # type: ignore


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "snapshot(*args, **kwargs): mark test to run as a snapshot test which sends traces to the test agent"
    )


def _request_token(request):
    token = ""
    token += request.module.__name__
    token += ".%s" % request.cls.__name__ if request.cls else ""
    token += f".{request.node.name}"
    return token


@pytest.fixture
def library_env() -> dict[str, str]:
    return {}


@pytest.fixture
def apm_test_server(request, library_env, test_id):
    """Request level definition of the library test server with the session Docker image built"""
    apm_test_server_image = scenarios.parametric.apm_test_server_definition
    new_env = dict(library_env)
    context.scenario.parametrized_tests_metadata[request.node.nodeid] = new_env

    new_env.update(apm_test_server_image.env)
    return dataclasses.replace(
        apm_test_server_image, container_name=f"{apm_test_server_image.container_name}-{test_id}", env=new_env
    )


@pytest.fixture
def test_server_log_file(apm_test_server, request) -> Generator[TextIO, None, None]:
    log_path = f"{context.scenario.host_log_folder}/outputs/{request.cls.__name__}/{request.node.name}/server_log.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w+", encoding="utf-8") as f:
        yield f
        f.seek(0)
        request.node._report_sections.append(
            ("teardown", f"{apm_test_server.lang.capitalize()} Library Output", "".join(f.readlines()))
        )


class _TestAgentAPI:
    def __init__(self, base_url: str, pytest_request: None):
        self._base_url = base_url
        self._session = requests.Session()
        self._pytest_request = pytest_request
        self.log_path = f"{context.scenario.host_log_folder}/outputs/{pytest_request.cls.__name__}/{pytest_request.node.name}/agent_api.log"  # type: ignore
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def _url(self, path: str) -> str:
        return urllib.parse.urljoin(self._base_url, path)

    def _write_log(self, log_type, json_trace):
        with open(self.log_path, "a") as log:
            log.write(f"\n{log_type}>>>>\n")
            log.write(json.dumps(json_trace))

    def traces(self, clear=False, **kwargs):
        resp = self._session.get(self._url("/test/session/traces"), **kwargs)
        if clear:
            self.clear()
        json = resp.json()
        self._write_log("traces", json)
        return json

    def set_remote_config(self, path, payload):
        resp = self._session.post(self._url("/test/session/responses/config/path"), json={"path": path, "msg": payload})
        assert resp.status_code == 202

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

    def add_remote_config(self, path, payload):
        current_rc = self.get_remote_config()
        current_rc.append({"path": path, "msg": payload})
        remote_config_payload = self._build_config_path_response(current_rc)
        resp = self._session.post(self._url("/test/session/responses/config"), remote_config_payload)
        assert resp.status_code == 202

    @staticmethod
    def _build_config_path_response(config: list):
        expires_date = datetime.datetime.strftime(
            datetime.datetime.now() + datetime.timedelta(days=1), "%Y-%m-%dT%H:%M:%SZ"
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

    def set_trace_delay(self, delay):
        resp = self._session.post(self._url("/test/settings"), json={"trace_request_delay": delay})
        assert resp.status_code == 202

    def raw_telemetry(self, clear=False, **kwargs):
        raw_reqs = self.requests()
        reqs = []
        for req in raw_reqs:
            if req["url"].endswith("/telemetry/proxy/api/v2/apmtelemetry"):
                reqs.append(req)
        if clear:
            self.clear()
        return reqs

    def telemetry(self, clear=False, **kwargs):
        resp = self._session.get(self._url("/test/session/apmtelemetry"), **kwargs)
        if clear:
            self.clear()
        return resp.json()

    def tracestats(self, **kwargs):
        resp = self._session.get(self._url("/test/session/stats"), **kwargs)
        json = resp.json()
        self._write_log("tracestats", json)
        return json

    def requests(self, **kwargs) -> list[AgentRequest]:
        resp = self._session.get(self._url("/test/session/requests"), **kwargs)
        json = resp.json()
        self._write_log("requests", json)
        return json

    def rc_requests(self, post_only=False):
        reqs = self.requests()
        rc_reqs = [r for r in reqs if r["url"].endswith("/v0.7/config") and (not (post_only) or r["method"] == "POST")]
        for r in rc_reqs:
            r["body"] = json.loads(base64.b64decode(r["body"]).decode("utf-8"))
        return rc_reqs

    def get_tracer_flares(self, **kwargs):
        resp = self._session.get(self._url("/test/session/tracerflares"), **kwargs)
        json = resp.json()
        self._write_log("tracerflares", json)
        return json

    def v06_stats_requests(self) -> list[AgentRequestV06Stats]:
        raw_requests = [r for r in self.requests() if "/v0.6/stats" in r["url"]]
        requests = []
        for raw in raw_requests:
            requests.append(
                AgentRequestV06Stats(
                    method=raw["method"],
                    url=raw["url"],
                    headers=raw["headers"],
                    body=decode_v06_stats(base64.b64decode(raw["body"])),
                )
            )
        return requests

    def clear(self, **kwargs) -> None:
        self._session.get(self._url("/test/session/clear"), **kwargs)

    def info(self, **kwargs):
        resp = self._session.get(self._url("/info"), **kwargs)

        if resp.status_code != 200:
            message = f"Test agent unexpected {resp.status_code} response: {resp.text}"
            logger.error(message)
            raise ValueError(message)

        json = resp.json()
        self._write_log("info", json)
        return json

    @contextlib.contextmanager
    def snapshot_context(self, token, ignores=None):
        ignores = ignores or []
        try:
            resp = self._session.get(self._url("/test/session/start?test_session_token=%s" % token))
            if resp.status_code != 200:
                # The test agent returns nice error messages we can forward to the user.
                raise RuntimeError(resp.text)
        except Exception as e:
            raise RuntimeError(f"Could not connect to test agent: {e}") from e
        else:
            yield self
            # Query for the results of the test.
            resp = self._session.get(
                self._url("/test/session/snapshot?ignores=%s&test_session_token=%s" % (",".join(ignores), token))
            )
            if resp.status_code != 200:
                raise RuntimeError(resp.text)

    def wait_for_num_traces(
        self, num: int, clear: bool = False, wait_loops: int = 30, sort_by_start: bool = True
    ) -> list[Trace]:
        """Wait for `num` traces to be received from the test agent.

        Returns after the number of traces has been received or raises otherwise after 2 seconds of polling.

        When sort_by_start=True returned traces are sorted by the span start time to simplify assertions by knowing that returned traces are in the same order as they have been created.
        """
        num_received = None
        for i in range(wait_loops):
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
                        return sorted(traces, key=lambda trace: trace[0]["start"])
                    return traces
            time.sleep(0.1)
        raise ValueError(
            "Number (%r) of traces not available from test agent, got %r:\n%r" % (num, num_received, traces)
        )

    def wait_for_num_spans(
        self, num: int, clear: bool = False, wait_loops: int = 30, sort_by_start: bool = True
    ) -> list[Trace]:
        """Wait for `num` spans to be received from the test agent.

        Returns after the number of spans has been received or raises otherwise after 2 seconds of polling.

        When sort_by_start=True returned traces are sorted by the span start time to simplify assertions by knowing that returned traces are in the same order as they have been created.
        """
        num_received = None
        for i in range(wait_loops):
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
                        return sorted(traces, key=lambda trace: trace[0]["start"])
                    return traces
            time.sleep(0.1)
        raise ValueError("Number (%r) of spans not available from test agent, got %r" % (num, num_received))

    def wait_for_telemetry_event(self, event_name: str, clear: bool = False, wait_loops: int = 200):
        """Wait for and return the given telemetry event from the test agent."""
        for i in range(wait_loops):
            try:
                events = self.telemetry(clear=False)
            except requests.exceptions.RequestException:
                pass
            else:
                for event in events:
                    if event["request_type"] == "message-batch":
                        for message in event["payload"]:
                            if message["request_type"] == event_name:
                                if message.get("application", {}).get("language_version") != "SIDECAR":
                                    if clear:
                                        self.clear()
                                    return message
                    elif event["request_type"] == event_name:
                        if event.get("application", {}).get("language_version") != "SIDECAR":
                            if clear:
                                self.clear()
                            return event
            time.sleep(0.01)
        raise AssertionError("Telemetry event %r not found" % event_name)

    def wait_for_rc_apply_state(
        self,
        product: str,
        state: RemoteConfigApplyState,
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
                rc_reqs = self.rc_requests(post_only)
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
                                # this condition prevent to spam logs, because the last knwon state
                                # will probably be the same as the current state
                                last_known_state = cfg_state["apply_state"]
                                logger.debug(f"Apply state {cfg_state['apply_state']} does not match {state}")
                        else:
                            logger.info(f"Found apply state {state} for product {product}")
                            if clear:
                                self.clear()
                            return cfg_state
            time.sleep(0.01)
        raise AssertionError("No RemoteConfig apply status found, got requests %r" % rc_reqs)

    def wait_for_rc_capabilities(self, capabilities: Iterable[int] = (), wait_loops: int = 100):
        """Wait for the given RemoteConfig apply state to be received by the test agent."""
        rc_reqs = []
        capabilities_seen = set()
        for i in range(wait_loops):
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
                        capabilities_seen.add(remoteconfig.human_readable_capabilities(int_capabilities))
                        if all((int_capabilities >> c) & 1 for c in capabilities):
                            return int_capabilities
            time.sleep(0.01)
        raise AssertionError("No RemoteConfig capabilities found, got capabilites %r" % capabilities_seen)

    def wait_for_tracer_flare(self, case_id: str | None = None, clear: bool = False, wait_loops: int = 100):
        """Wait for the tracer-flare to be received by the test agent."""
        for i in range(wait_loops):
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


@pytest.fixture(scope="session")
def docker() -> str | None:
    """Fixture to ensure docker is ready to use on the system."""
    # Redirect output to /dev/null since we just care if we get a successful response code.
    r = subprocess.run(
        ["docker", "info"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=default_subprocess_run_timeout,
        check=False,
    )
    if r.returncode != 0:
        pytest.exit(
            "Docker is not running and is required to run the shared APM library tests. Start docker and try running the tests again.",
            returncode=1,
        )
    return shutil.which("docker")


@pytest.fixture
def docker_network(test_id: str) -> Generator[str, None, None]:
    network = scenarios.parametric.create_docker_network(test_id)

    try:
        yield network.name
    finally:
        try:
            network.remove()
        except:
            # It's possible (why?) of having some container not stopped.
            # If it happen, failing here makes stdout tough to understance.
            # Let's ignore this, later calls will clean the mess
            logger.info("Failed to remove network, ignoring the error")


@pytest.fixture
def test_agent_port() -> int:
    """Returns the port exposed inside the agent container"""
    return 8126


@pytest.fixture
def test_agent_log_file(request) -> Generator[TextIO, None, None]:
    log_path = f"{context.scenario.host_log_folder}/outputs/{request.cls.__name__}/{request.node.name}/agent_log.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w+", encoding="utf-8") as f:
        yield f
        f.seek(0)
        agent_output = ""
        for line in f:
            # Remove log lines that are not relevant to the test
            if "GET /test/session/traces" in line:
                continue
            if "GET /test/session/requests" in line:
                continue
            if "GET /test/session/clear" in line:
                continue
            if "GET /test/session/apmtelemetry" in line:
                continue
            agent_output += line
        request.node._report_sections.append(("teardown", "Test Agent Output", agent_output))


@pytest.fixture
def test_agent_container_name(test_id) -> str:
    return f"ddapm-test-agent-{test_id}"


@pytest.fixture
def test_agent_hostname(test_agent_container_name: str) -> str:
    return test_agent_container_name


@pytest.fixture
def test_agent(
    worker_id: str,
    docker_network: str,
    request,
    test_agent_container_name: str,
    test_agent_port: int,
    test_agent_log_file: TextIO,
):
    env = {}
    if os.getenv("DEV_MODE") is not None:
        env["SNAPSHOT_CI"] = "0"

    # (meta_tracer_version_header) Not all clients (go for example) submit the tracer version
    # (trace_content_length) go client doesn't submit content length header
    env["ENABLED_CHECKS"] = "trace_count_header"

    host_port = scenarios.parametric.get_host_port(worker_id, 4600)

    with scenarios.parametric.docker_run(
        image=scenarios.parametric.TEST_AGENT_IMAGE,
        name=test_agent_container_name,
        command=[],
        env=env,
        volumes={f"{os.getcwd()}/snapshots": "/snapshots"},
        host_port=host_port,
        container_port=test_agent_port,
        log_file=test_agent_log_file,
        network=docker_network,
    ):
        client = _TestAgentAPI(base_url=f"http://localhost:{host_port}", pytest_request=request)
        time.sleep(0.2)  # intial wait time, the trace agent takes 200ms to start
        for _ in range(100):
            try:
                resp = client.info()
            except Exception as e:
                logger.debug(f"Wait for 0.1s for the test agent to be ready {e}")
                time.sleep(0.1)
            else:
                if resp["version"] != "test":
                    message = f"""Agent version {resp['version']} is running instead of the test agent.
                    Stop the agent on port {test_agent_port} and try again."""
                    pytest.fail(message, pytrace=False)

                logger.info("Test agent is ready")
                break
        else:
            logger.error("Could not connect to test agent")
            pytest.fail(
                f"Could not connect to test agent, check the log file {test_agent_log_file.name}.", pytrace=False
            )

        # If the snapshot mark is on the test case then do a snapshot test
        marks = [m for m in request.node.iter_markers(name="snapshot")]
        assert len(marks) < 2, "Multiple snapshot marks detected"
        if marks:
            snap = marks[0]
            assert len(snap.args) == 0, "only keyword arguments are supported by the snapshot decorator"
            if "token" not in snap.kwargs:
                snap.kwargs["token"] = _request_token(request).replace(" ", "_").replace(os.path.sep, "_")
            with client.snapshot_context(**snap.kwargs):
                yield client
        else:
            yield client


@pytest.fixture
def test_library(
    worker_id: str,
    docker_network: str,
    test_agent_port: str,
    test_agent_container_name: str,
    apm_test_server: APMLibraryTestServer,
    test_server_log_file: TextIO,
) -> Generator[APMLibrary, None, None]:
    env = {
        "DD_TRACE_DEBUG": "true",
        "DD_TRACE_AGENT_URL": f"http://{test_agent_container_name}:{test_agent_port}",
        "DD_AGENT_HOST": test_agent_container_name,
        "DD_TRACE_AGENT_PORT": test_agent_port,
        "APM_TEST_CLIENT_SERVER_PORT": str(apm_test_server.container_port),
        "DD_TRACE_OTEL_ENABLED": "true",
    }
    for k, v in apm_test_server.env.items():
        # Don't set env vars with a value of None
        if v is not None:
            env[k] = v
        elif k in env:
            del env[k]

    apm_test_server.host_port = scenarios.parametric.get_host_port(worker_id, 4500)

    with scenarios.parametric.docker_run(
        image=apm_test_server.container_tag,
        name=apm_test_server.container_name,
        command=apm_test_server.container_cmd,
        env=env,
        host_port=apm_test_server.host_port,
        container_port=apm_test_server.container_port,
        volumes=apm_test_server.volumes,
        log_file=test_server_log_file,
        network=docker_network,
    ) as container:
        apm_test_server.container = container

        test_server_timeout = 60

        if apm_test_server.host_port is None:
            raise RuntimeError("Internal error, no port has been assigned", 1)

        client = APMLibraryClient(
            f"http://localhost:{apm_test_server.host_port}", test_server_timeout, apm_test_server.container
        )

        tracer = APMLibrary(client, apm_test_server.lang)
        yield tracer
