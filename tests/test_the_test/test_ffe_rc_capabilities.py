"""Regressions for RC capability assertions, gated startup, and update acknowledgement."""

import base64
import hashlib
import json
from collections.abc import Generator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from typing import Any
from unittest.mock import MagicMock, patch

from requests.exceptions import ReadTimeout

from tests.parametric.test_ffe.utils import assert_dependent_flag_capability, deliver, ffe_requests, start_and_deliver
from utils import features, pytest, scenarios
from utils.dd_constants import Capabilities, RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI, ParametricTestClientApi

DEPENDENT_FLAG_MASK = 1 << Capabilities.FFE_FLAG_DEPENDENT_FLAG_VARIANT_KEY_V1
FLAG_CONFIGURATION_MASK = 1 << Capabilities.FFE_FLAG_CONFIGURATION_RULES


def _request(mask: int, *, byte_array: bool) -> dict[str, Any]:
    raw = mask.to_bytes(7, byteorder="big")
    return {
        "body": {
            "client": {"id": "ffe-client", "capabilities": list(raw) if byte_array else base64.b64encode(raw).decode()}
        }
    }


HTTP_TIMEOUT_SECONDS = 1
HELPER_COMPLETION_TIMEOUT_SECONDS = 5
SILENT_RESPONSE_TIMEOUT_SECONDS = 2 * HELPER_COMPLETION_TIMEOUT_SECONDS


@contextmanager
def _ffe_http_client(
    *, response_delay_seconds: float = SILENT_RESPONSE_TIMEOUT_SECONDS
) -> Generator[tuple[ParametricTestClientApi, Event, Event], None, None]:
    requested = Event()
    release = Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(404)
            self.end_headers()

        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            requested.set()
            release.wait(timeout=response_delay_seconds)
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        worker = Thread(target=server.serve_forever)
        worker.start()
        try:
            library = ParametricTestClientApi(
                "python", f"http://127.0.0.1:{server.server_port}", HTTP_TIMEOUT_SECONDS, MagicMock(status="running")
            )
            try:
                yield library, requested, release
            finally:
                release.set()
                library._session.close()  # noqa: SLF001 - close the HTTP session owned by this control
        finally:
            server.shutdown()
            worker.join()


@scenarios.test_the_test
@features.not_reported
class Test_FFE_RC_Capability_Assertion:
    @pytest.mark.parametrize("byte_array", [False, True])
    def test_supported_and_legacy(self, *, byte_array: bool) -> None:
        assert_dependent_flag_capability(
            [_request(FLAG_CONFIGURATION_MASK | DEPENDENT_FLAG_MASK, byte_array=byte_array)], supported=True
        )
        assert_dependent_flag_capability([_request(FLAG_CONFIGURATION_MASK, byte_array=byte_array)], supported=False)

    @pytest.mark.parametrize("byte_array", [False, True])
    def test_missing_bit_fails_even_if_later_poll_recovers(self, *, byte_array: bool) -> None:
        requests = [
            _request(FLAG_CONFIGURATION_MASK, byte_array=byte_array),
            _request(FLAG_CONFIGURATION_MASK | DEPENDENT_FLAG_MASK, byte_array=byte_array),
        ]
        with pytest.raises(AssertionError, match=f"bit {Capabilities.FFE_FLAG_DEPENDENT_FLAG_VARIANT_KEY_V1}=True"):
            assert_dependent_flag_capability(requests, supported=True)

    def test_false_advertisement_fails(self) -> None:
        with pytest.raises(AssertionError, match=f"bit {Capabilities.FFE_FLAG_DEPENDENT_FLAG_VARIANT_KEY_V1}=False"):
            assert_dependent_flag_capability([_request(DEPENDENT_FLAG_MASK, byte_array=False)], supported=False)

    def test_no_traffic_is_not_a_pass(self) -> None:
        with pytest.raises(AssertionError, match="No FFE_FLAGS RC requests"):
            assert_dependent_flag_capability([], supported=False)


RC_PATH = "datadog/2/FFE_FLAGS/flags/config"


def _poll(
    *, content: str = "", acknowledged: bool = False, product: str = "FFE_FLAGS", version: int = 1
) -> dict[str, Any]:
    request = _request(FLAG_CONFIGURATION_MASK | DEPENDENT_FLAG_MASK, byte_array=False)
    request["method"] = "GET"
    request["body"]["client"].update(
        products=["FFE_FLAGS"],
        state={
            "config_states": [
                {
                    "id": "flags",
                    "product": product,
                    "version": version,
                    "apply_state": (
                        RemoteConfigApplyState.ACKNOWLEDGED.value
                        if acknowledged
                        else RemoteConfigApplyState.UNACKNOWLEDGED.value
                    ),
                }
            ]
        },
    )
    request["body"]["cached_target_files"] = (
        [{"path": RC_PATH, "hashes": [{"algorithm": "sha256", "hash": content}]}] if content else []
    )
    return request


@scenarios.test_the_test
@features.not_reported
class Test_FFE_RC_Delivery:
    def test_versioned_publication_preserves_payload_and_versions(self) -> None:
        agent = object.__new__(TestAgentAPI)
        agent.host = "localhost"
        agent.host_port = 8126
        session = MagicMock()
        session.post.return_value.status_code = 202
        with patch.object(agent, "_session", session, create=True):
            for version in (1, 2):
                payload = {"flags": {"revision": version}}
                agent.set_remote_config(path=RC_PATH, payload=payload, version=version)
                args, kwargs = session.post.call_args
                assert args == ("http://localhost:8126/test/session/responses/config",)
                response = json.loads(kwargs["data"])
                metadata = json.loads(base64.b64decode(response["targets"]))["signed"]
                assert metadata["version"] == version
                target = metadata["targets"][RC_PATH]
                assert target["custom"]["v"] == version
                assert response["client_configs"] == [RC_PATH]
                assert response["target_files"][0]["path"] == RC_PATH
                raw = base64.b64decode(response["target_files"][0]["raw"])
                assert json.loads(raw) == payload
                assert target["hashes"]["sha256"] == hashlib.sha256(raw).hexdigest()
                assert target["length"] == len(raw)

    def test_get_and_post_polls_keep_product_filter(self) -> None:
        agent = MagicMock(spec=TestAgentAPI)
        get = _poll()
        post = _poll()
        post["method"] = "POST"
        unrelated = _poll()
        unrelated["body"]["client"]["products"] = ["APM_TRACING"]
        agent.rc_requests.side_effect = lambda *, post_only=False: ([post] if post_only else [get, unrelated, post])
        assert ffe_requests(agent) == [get, post]

    def test_update_requires_delivered_version_ack(self) -> None:
        agent = MagicMock(spec=TestAgentAPI)
        old = _poll(content="old", acknowledged=True)
        new_without_ack = _poll(content="new", version=2)
        wrong_product = _poll(content="new", acknowledged=True, product="APM_TRACING", version=2)
        new_with_stale_ack = _poll(content="new", acknowledged=True, version=1)
        new_ack = _poll(content="new", acknowledged=True, version=2)
        agent.rc_requests.side_effect = [
            [old],
            [old, old],
            [old, old, new_without_ack],
            [old, old, new_without_ack, wrong_product],
            [old, old, new_without_ack, wrong_product, new_with_stale_ack],
            [old, old, new_without_ack, wrong_product, new_with_stale_ack, new_ack],
        ]
        with patch("tests.parametric.test_ffe.utils.time.sleep"):
            deliver(agent, config_id="flags", payload={"flags": {}}, version=2)
        agent.set_remote_config.assert_called_once_with(path=RC_PATH, payload={"flags": {}}, version=2)
        assert agent.rc_requests.call_count == 6
        agent.clear.assert_not_called()

    def test_null_rc_state_waits_for_ack(self) -> None:
        agent = MagicMock(spec=TestAgentAPI)
        empty = _poll()
        empty["body"]["cached_target_files"] = None
        empty["body"]["client"]["state"]["config_states"] = None
        new_without_state = _poll(content="new")
        new_without_state["body"]["client"]["state"]["config_states"] = None
        new_ack = _poll(content="new", acknowledged=True)
        agent.rc_requests.side_effect = [
            [empty],
            [empty, empty],
            [empty, empty, new_without_state],
            [empty, empty, new_without_state, new_ack],
        ]
        with patch("tests.parametric.test_ffe.utils.time.sleep"):
            deliver(agent, config_id="flags", payload={"flags": {}}, version=1)
        assert agent.rc_requests.call_count == 4
        agent.clear.assert_not_called()

    @pytest.mark.parametrize("cache_state", ["omitted", "null", "empty", "unchanged"])
    def test_versioned_ack_does_not_require_target_caching(self, cache_state: str) -> None:
        agent = MagicMock(spec=TestAgentAPI)
        old = _poll(content="old", acknowledged=True)
        unacknowledged = _poll(content="old", version=2)
        acknowledged = _poll(content="old", acknowledged=True, version=2)
        for request in (old, unacknowledged, acknowledged):
            if cache_state == "omitted":
                del request["body"]["cached_target_files"]
            elif cache_state == "null":
                request["body"]["cached_target_files"] = None
            elif cache_state == "empty":
                request["body"]["cached_target_files"] = []
        agent.rc_requests.side_effect = [
            [old],
            [old, unacknowledged],
            [old, unacknowledged, acknowledged],
        ]
        with (
            patch("tests.parametric.test_ffe.utils.time.monotonic", side_effect=[0, 0, 0, 11]),
            patch("tests.parametric.test_ffe.utils.time.sleep"),
        ):
            deliver(agent, config_id="flags", payload={"flags": {}}, version=2)
        agent.set_remote_config.assert_called_once_with(path=RC_PATH, payload={"flags": {}}, version=2)
        assert agent.rc_requests.call_count == 3
        agent.clear.assert_not_called()

    @pytest.mark.parametrize("content", ["old", "new"])
    def test_stale_ack_times_out(self, content: str) -> None:
        agent = MagicMock(spec=TestAgentAPI)
        old = _poll(content="old", acknowledged=True)
        stale = _poll(content=content, acknowledged=True, version=1)
        agent.rc_requests.side_effect = [[old], [old, stale]]
        with (
            patch("tests.parametric.test_ffe.utils.time.monotonic", side_effect=[0, 0, 11]),
            patch("tests.parametric.test_ffe.utils.time.sleep"),
            pytest.raises(AssertionError, match="did not acknowledge new configuration content"),
        ):
            deliver(agent, config_id="flags", payload={"flags": {}}, version=2)

    @pytest.mark.parametrize("blocking", [True, False])
    @pytest.mark.parametrize("supported", [True, False])
    def test_cold_start_delivers_before_requiring_readiness(self, *, blocking: bool, supported: bool) -> None:
        agent = MagicMock(spec=TestAgentAPI)
        library = MagicMock(spec=ParametricTestClientApi)
        starting = Event()
        delivered = Event()
        observed: list[dict[str, Any]] = []

        def start() -> bool:
            starting.set()
            if blocking:
                assert delivered.wait(timeout=5), "Startup blocked waiting for configuration"
            return delivered.is_set()

        def polls() -> list[dict[str, Any]]:
            assert starting.wait(timeout=5), "Provider startup was never triggered"
            poll = _poll(content="new" if delivered.is_set() else "", acknowledged=delivered.is_set())
            poll["body"]["client"]["capabilities"] = _request(
                FLAG_CONFIGURATION_MASK | (DEPENDENT_FLAG_MASK if supported else 0), byte_array=False
            )["body"]["client"]["capabilities"]
            observed.append(poll)
            return list(observed)

        def configure(*, path: str, payload: dict[str, Any], version: int) -> None:
            assert version == 1
            assert path == RC_PATH
            assert payload == {"flags": {}}
            assert len(observed) >= 3, "Configuration delivered before observing capabilities"
            delivered.set()

        library.ffe_start.side_effect = start
        agent.rc_requests.side_effect = polls
        agent.set_remote_config.side_effect = configure
        start_and_deliver(agent, library, config_id="flags", payload={"flags": {}}, version=1, supported=supported)
        assert delivered.is_set()
        library.terminate.assert_not_called()
        assert library.ffe_start.call_count == (1 if blocking else 2)
        agent.clear.assert_not_called()

    @pytest.mark.parametrize("failure_stage", ["capabilities", "delivery", "readiness", "retry"])
    def test_failed_startup_terminates_before_joining(self, failure_stage: str) -> None:
        agent = MagicMock(spec=TestAgentAPI)
        library = MagicMock(spec=ParametricTestClientApi)
        starting = Event()
        stopped = Event()
        finished = Event()
        failure = (
            TimeoutError(f"Failed during {failure_stage}")
            if failure_stage in ("readiness", "retry")
            else AssertionError(f"Failed during {failure_stage}")
        )

        def start() -> bool:
            if failure_stage == "retry" and library.ffe_start.call_count == 1:
                return False
            starting.set()
            try:
                assert stopped.wait(timeout=5), "Startup was joined before the application was terminated"
                raise ConnectionError("Application terminated")
            finally:
                finished.set()

        def observe(*_args: object, **_kwargs: object) -> None:
            if failure_stage != "retry":
                assert starting.wait(timeout=5)
            if failure_stage == "capabilities":
                raise failure

        def deliver_config(*_args: object, **_kwargs: object) -> None:
            if failure_stage == "delivery":
                raise failure

        original_result = Future.result
        result_calls = 0

        def result(future: Future[bool], timeout: float | None = None) -> bool:
            nonlocal result_calls
            result_calls += 1
            if failure_stage == "readiness" or (failure_stage == "retry" and result_calls == 2):
                assert starting.wait(timeout=5)
                raise failure
            return original_result(future, timeout=timeout)

        library.ffe_start.side_effect = start
        library.terminate.side_effect = stopped.set
        with (
            patch("tests.parametric.test_ffe.utils.observe_polls", side_effect=observe),
            patch("tests.parametric.test_ffe.utils.deliver", side_effect=deliver_config),
            patch.object(Future, "result", result),
            pytest.raises((AssertionError, TimeoutError)) as raised,
        ):
            start_and_deliver(agent, library, config_id="flags", payload={"flags": {}}, version=1, supported=True)
        assert raised.value is failure
        library.terminate.assert_called_once_with()
        assert finished.is_set(), "Startup worker leaked beyond the helper"

    @pytest.mark.parametrize("termination_fails", [False, True])
    def test_startup_http_request_finishes_when_cleanup_fails(self, *, termination_fails: bool) -> None:
        failure = AssertionError("Missing dependent flag capability")
        with _ffe_http_client() as (library, requested, release), ThreadPoolExecutor(max_workers=1) as executor:

            def observe(*_args: object, **_kwargs: object) -> None:
                assert requested.wait(timeout=HELPER_COMPLETION_TIMEOUT_SECONDS)
                raise failure

            if termination_fails:
                library.container.kill.side_effect = RuntimeError("Docker termination failed")
            else:
                library.container.kill.side_effect = lambda **_kwargs: release.set()

            with patch("tests.parametric.test_ffe.utils.observe_polls", side_effect=observe):
                pending = executor.submit(
                    start_and_deliver,
                    MagicMock(spec=TestAgentAPI),
                    library,
                    config_id="flags",
                    payload={"flags": {}},
                    version=1,
                    supported=True,
                )
                try:
                    with pytest.raises(AssertionError) as raised:
                        pending.result(timeout=HELPER_COMPLETION_TIMEOUT_SECONDS)
                    assert raised.value is failure
                    library.container.kill.assert_called_once_with(signal="SIGKILL")
                    if termination_fails:
                        assert "Docker termination failed" in " ".join(failure.__notes__)
                        assert not release.is_set(), "Server was released before the HTTP timeout"
                finally:
                    # Ensure even a regression cannot hang the executor's cleanup.
                    release.set()

    def test_startup_http_request_accepts_delayed_response(self) -> None:
        with _ffe_http_client(response_delay_seconds=0.2) as (library, requested, _release):
            assert library.ffe_start()
            assert requested.is_set()

    def test_evaluation_http_request_times_out_on_silent_response(self) -> None:
        with _ffe_http_client() as (library, requested, release), ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(
                library.ffe_evaluate,
                flag="child",
                variation_type="STRING",
                default_value="caller-default",
                targeting_key="subject",
            )
            try:
                assert requested.wait(timeout=HELPER_COMPLETION_TIMEOUT_SECONDS)
                with pytest.raises(ReadTimeout):
                    pending.result(timeout=HELPER_COMPLETION_TIMEOUT_SECONDS)
                assert not release.is_set(), "Server was released before the HTTP timeout"
            finally:
                # Release the server even if a regression leaves the HTTP request blocked.
                release.set()
