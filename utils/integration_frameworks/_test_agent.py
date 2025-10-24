import base64
import contextlib
from http import HTTPStatus
import json
from pathlib import Path
import time
from typing import TypedDict, Any
import urllib.parse

import pytest
import requests

from utils._logger import logger
from utils.parametric.spec.trace import Trace

from ._core import get_host_port

IGNORE_PARAMS_FOR_TEST_NAME = (
    "test_agent",
    "test_library",
)


class AgentRequest(TypedDict):
    method: str
    url: str
    headers: dict[str, str]
    body: str


class _TestAgentAPI:
    """Abstracts everything about test agent. TODO : share this with parametric test"""

    def __init__(self, host_log_folder: str, host: str, worker_id: str, pytest_request: pytest.FixtureRequest):
        self.host = host
        self.agent_port = get_host_port(worker_id, 4600)
        self._session = requests.Session()
        self._pytest_request = pytest_request
        self.log_path = (
            f"{host_log_folder}/outputs/{pytest_request.cls.__name__}/{pytest_request.node.name}/agent_api.log"
        )
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)

    def _url(self, path: str) -> str:
        return urllib.parse.urljoin(f"http://{self.host}:{self.agent_port}", path)

    def _write_log(self, log_type: str, json_trace: dict | list | None):
        with open(self.log_path, "a") as log:
            log.write(f"\n{log_type}>>>>\n")
            log.write(json.dumps(json_trace))

    def traces(self, **kwargs: dict) -> list[Trace]:
        resp = self._session.get(self._url("/test/session/traces"), **kwargs)  # type: ignore[arg-type]
        resp_json = resp.json()
        self._write_log("traces", resp_json)
        return resp_json

    def requests(self) -> list[AgentRequest]:
        resp = self._session.get(self._url("/test/session/requests"))
        resp_json = resp.json()
        self._write_log("requests", resp_json)
        return resp_json

    def clear(self) -> None:
        self._session.get(self._url("/test/session/clear"))

    def info(self):
        resp = self._session.get(self._url("/info"))

        if resp.status_code != HTTPStatus.OK:
            message = f"Test agent unexpected {resp.status_code} response: {resp.text}"
            logger.error(message)
            raise ValueError(message)

        resp_json = resp.json()
        self._write_log("info", resp_json)
        return resp_json

    def llmobs_requests(self) -> list[Any]:
        reqs = [r for r in self.requests() if r["url"].endswith("/evp_proxy/v2/api/v2/llmobs")]

        events = []
        for r in reqs:
            decoded_body = base64.b64decode(r["body"])
            events.append(json.loads(decoded_body))
        return events

    def llmobs_evaluations_requests(self):
        reqs = [
            r
            for r in self.requests()
            if r["url"].endswith("/evp_proxy/v2/api/intake/llm-obs/v1/eval-metric")
            or r["url"].endswith("/evp_proxy/v2/api/intake/llm-obs/v2/eval-metric")
        ]

        return [json.loads(base64.b64decode(r["body"])) for r in reqs]

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

    @contextlib.contextmanager
    def vcr_context(self, cassette_prefix: str = ""):
        """Starts a VCR context manager, which will prefix all recorded cassettes from the test agent with the
        given prefix. If no prefix is provided, the test name will be used.
        """
        test_name = cassette_prefix or self._pytest_request.node.originalname

        for param in self._pytest_request.node.callspec.params:
            if param not in IGNORE_PARAMS_FOR_TEST_NAME:
                param_value = self._pytest_request.node.callspec.params[param]
                test_name += f"_{param}_{param_value}"

        try:
            resp = self._session.post(self._url("/vcr/test/start"), json={"test_name": test_name})
            resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Could not connect to test agent: {e}") from e
        else:
            yield self
            resp = self._session.post(self._url("/vcr/test/stop"))
            resp.raise_for_status()

    def wait_for_num_traces(self, num: int, *, wait_loops: int = 30, sort_by_start: bool = True) -> list[Trace]:
        """Wait for `num` traces to be received from the test agent.

        Returns after the number of traces has been received or raises otherwise after 2 seconds of polling.

        When sort_by_start=True returned traces are sorted by the span start time to simplify assertions by knowing that
        returned traces are in the same order as they have been created.
        """
        num_received = None
        traces = []
        for _ in range(wait_loops):
            try:
                traces = self.traces()
            except requests.exceptions.RequestException:
                pass
            else:
                num_received = len(traces)
                if num_received == num:
                    if sort_by_start:
                        for trace in traces:
                            # The testagent may receive spans and trace chunks in any order,
                            # so we sort the spans by start time if needed
                            trace.sort(key=lambda x: x["start"])
                        return sorted(traces, key=lambda t: t[0]["start"])
                    return traces
            time.sleep(0.1)
        raise ValueError(f"Number ({num}) of traces not available from test agent, got {num_received}:\n{traces}")

    def wait_for_llmobs_requests(self, num: int, *, wait_loops: int = 30, sort_by_start: bool = True) -> list[Any]:
        """Wait for `num` LLMobs requests to be received from the test agent."""
        num_received = None
        llmobs_requests = []
        for _ in range(wait_loops):
            try:
                llmobs_requests = self.llmobs_requests()
            except requests.exceptions.RequestException:
                pass
            else:
                num_received = len(llmobs_requests)
                if num_received == num:
                    if sort_by_start:
                        for trace in llmobs_requests:
                            # The testagent may receive spans and trace chunks in any order,
                            # so we sort the spans by start time if needed
                            trace.sort(key=lambda x: x["start_ns"])
                        return sorted(llmobs_requests, key=lambda t: t[0]["start_ns"])
                    return llmobs_requests
            time.sleep(0.1)
        raise ValueError(
            f"Number ({num}) of traces not available from test agent, got {num_received}:\n{llmobs_requests}"
        )

    def wait_for_llmobs_evaluations_requests(self, num: int, *, wait_loops: int = 30) -> list[Any]:
        """Wait for `num` LLMobs evaluations requests to be received from the test agent."""
        num_received = None
        llmobs_evaluations_requests = []
        for _ in range(wait_loops):
            try:
                llmobs_evaluations_requests = self.llmobs_evaluations_requests()
            except requests.exceptions.RequestException:
                pass
            else:
                num_received = len(llmobs_evaluations_requests)
                if num_received == num:
                    return llmobs_evaluations_requests
            time.sleep(0.1)
        raise ValueError(
            f"""Number ({num}) of LLMobs evaluations requests not available from test agent, got {num_received}:
            {llmobs_evaluations_requests}"""
        )
