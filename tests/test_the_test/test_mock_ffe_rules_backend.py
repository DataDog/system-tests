"""Check the HTTP fixtures used by the standalone configuration-helper tests."""

import base64

import requests

from utils import features, pytest, scenarios
from utils.docker_fixtures._core import HOST_GATEWAY_EXTRA_HOSTS, extra_hosts_for_environment
from utils.mocked_backend.ffe_rules import CONFIG_PATH, WIRE_FIXTURE, MockFFERulesBackendServer


@scenarios.test_the_test
@features.not_reported
class Test_Mock_FFE_Rules_Backend:
    def test_protobuf_and_request_capture(self) -> None:
        server = MockFFERulesBackendServer(port=0)
        try:
            for channel in ("client", "server"):
                response = requests.get(
                    f"{server.base_url}{CONFIG_PATH}/{channel}",
                    params={"dd_env": "test env"},
                    headers={"dd-client-token": "dummy-token"},
                    timeout=5,
                )
                assert response.status_code == 200
                assert response.headers["Content-Type"] == "application/protobuf"
                assert response.headers["ETag"] == WIRE_FIXTURE["rules"]["etag"]
                assert response.content == base64.b64decode(WIRE_FIXTURE["rules"]["response"])
            assert len(server.requests) == 2
            assert server.requests[0]["path"] == f"{CONFIG_PATH}/client?dd_env=test+env"
            assert server.requests[0]["headers"]["dd-client-token"] == "dummy-token"
            assert extra_hosts_for_environment({"SYSTEM_TESTS_FFE_RULES_BASE_URL": server.library_base_url}) == (
                HOST_GATEWAY_EXTRA_HOSTS
            )
        finally:
            server.close()

    @pytest.mark.parametrize(
        ("mode", "status", "content_type", "body"),
        [
            ("forbidden", 403, "application/protobuf", b"private-response-body"),
            ("server_error", 500, "application/protobuf", b"private-response-body"),
            ("malformed", 200, "application/protobuf", b"\xff"),
            ("empty", 200, "application/protobuf", b""),
            ("wrong_content_type", 200, "application/json", b"{}"),
        ],
    )
    def test_failure_responses(self, mode: str, status: int, content_type: str, body: bytes) -> None:
        server = MockFFERulesBackendServer(port=0)
        try:
            server.response = mode
            response = requests.get(f"{server.base_url}{CONFIG_PATH}/client", timeout=5)
            assert response.status_code == status
            assert response.headers["Content-Type"] == content_type
            assert response.content == body
        finally:
            server.close()

    def test_redirect_records_destination_requests(self) -> None:
        server = MockFFERulesBackendServer(port=0)
        try:
            server.response = "redirect"
            response = requests.get(f"{server.base_url}{CONFIG_PATH}/client", allow_redirects=False, timeout=5)
            assert response.status_code == 302
            assert response.headers["Location"] == f"{server.library_base_url}/redirected"
            server.response = "valid"
            requests.get(f"{server.base_url}/redirected", timeout=5).raise_for_status()
            assert len(server.requests) == 2
            assert server.requests[1]["path"] == "/redirected"
        finally:
            server.close()

    @pytest.mark.parametrize(
        ("mode", "error"),
        [("disconnect", requests.ConnectionError), ("truncated_body", requests.exceptions.ChunkedEncodingError)],
    )
    def test_interrupted_responses(self, mode: str, error: type[requests.RequestException]) -> None:
        server = MockFFERulesBackendServer(port=0)
        try:
            server.response = mode
            with pytest.raises(error):
                requests.get(f"{server.base_url}{CONFIG_PATH}/client", timeout=5)
            assert len(server.requests) == 1
        finally:
            server.close()
