"""Check the HTTP fixtures used by the standalone configuration-helper tests."""

import base64

import requests

from utils import features, pytest, scenarios
from utils.docker_fixtures._core import HOST_GATEWAY_EXTRA_HOSTS, extra_hosts_for_environment
from utils.mocked_backend import MockedBackendServer
from utils.mocked_backend.ffe import (
    RULES_CONFIG_PATH,
    UFC_RESPONSE_TYPE,
    ResponseFormat,
    load_rules_wire_fixture,
)

WIRE_FIXTURE = load_rules_wire_fixture()


@scenarios.test_the_test
@features.not_reported
class Test_Mock_FFE_Rules_Backend:
    @pytest.mark.parametrize(
        ("accept", "content_type"),
        [
            ("application/protobuf", "application/protobuf"),
            ("application/protobuf, */*", "application/protobuf"),
            ("text/plain, Application/Protobuf ; q=0.8, */*;q=0.1", "application/protobuf"),
            ("application/json", "application/json"),
            ("*/*", "application/json"),
            ("", "application/json"),
            ("application/protobuf;q=0, */*", "application/json"),
            ("application/protobuf;q=invalid, application/json", "application/json"),
            ("application/protobuf-other, */*", "application/json"),
        ],
    )
    def test_server_accept_header(self, accept: str, content_type: str) -> None:
        server = MockedBackendServer(port=0)
        try:
            response = requests.get(
                f"{server.base_url}{RULES_CONFIG_PATH}/server?dd_env=test",
                headers={"Accept": accept},
                timeout=5,
            )
            assert response.status_code == 200
            assert response.headers["Content-Type"] == content_type
            if content_type == "application/protobuf":
                assert response.content == base64.b64decode(WIRE_FIXTURE["rules"]["response"])
            else:
                assert response.json()["data"]["type"] == UFC_RESPONSE_TYPE
        finally:
            server.close()

    def test_server_negotiates_format_with_independent_response_timelines(self) -> None:
        server = MockedBackendServer(port=0)
        try:
            url = f"{server.base_url}{RULES_CONFIG_PATH}/server?dd_env=test"
            # Existing HTTP controls without a format still configure JSON.
            requests.post(
                f"{server.base_url}/system-tests/ffe/responses",
                json={"responses": ["unauthorized", "not_modified"]},
                timeout=5,
            ).raise_for_status()
            server.ffe_set_responses(["malformed", "valid"], response_format="protobuf")
            malformed = requests.get(url, headers={"Accept": "application/protobuf"}, timeout=5)
            assert malformed.content == b"\xff"

            assert requests.get(url, timeout=5).status_code == 401
            protobuf = requests.get(url, headers={"Accept": "application/protobuf"}, timeout=5)
            assert protobuf.content == base64.b64decode(WIRE_FIXTURE["rules"]["response"])

            assert requests.get(url, timeout=5).status_code == 304
            assert requests.get(url, timeout=5).status_code == 304
            assert server.ffe_get_status()["requests_total"] == 5
            assert len(server.ffe_get_requests()) == 5

            server.ffe_set_response("forbidden", response_format="protobuf")
            server.ffe_reset()
            assert server.ffe_get_requests() == []
            assert server.ffe_get_status()["requests_total"] == 0
            reset_response = requests.get(url, headers={"Accept": "application/protobuf"}, timeout=5)
            assert reset_response.status_code == 200
            assert reset_response.content == protobuf.content
            json_response = requests.get(url, timeout=5)
            assert json_response.status_code == 200
            assert json_response.headers["Content-Type"] == "application/json"
            assert json_response.json()["data"]["type"] == UFC_RESPONSE_TYPE
        finally:
            server.close()

    @pytest.mark.parametrize(
        ("response_format", "response_id"),
        [
            ("json", "forbidden"),
            ("json", "redirect"),
            ("json", "empty"),
            ("json", "wrong_content_type"),
            ("json", "delayed"),
            ("json", "delayed_body"),
            ("json", "disconnect"),
            ("json", "truncated_body"),
            ("protobuf", "unauthorized"),
            ("protobuf", "not_modified"),
            ("protobuf", "delayed_valid"),
            ("protobuf", "timeout"),
        ],
    )
    def test_rejects_response_ids_for_the_other_format(self, response_format: ResponseFormat, response_id: str) -> None:
        server = MockedBackendServer(port=0)
        try:
            server.ffe_set_response("unauthorized")
            server.ffe_set_response("forbidden", response_format="protobuf")
            status = server.ffe_get_status()
            error = f"unsupported {response_format} response: {response_id}"
            with pytest.raises(ValueError, match=error):
                server.ffe_set_response(response_id, response_format=response_format)
            with pytest.raises(ValueError, match=error):
                server.ffe_set_responses(["valid", response_id], response_format=response_format)

            # Direct HTTP clients must receive the same validation as the Python helper.
            response = requests.post(
                f"{server.base_url}/system-tests/ffe/responses",
                json={"responses": ["valid", response_id], "response_format": response_format},
                timeout=5,
            )
            assert response.status_code == 400
            assert response.json() == {"error": error}
            assert server.ffe_get_status() == status

            # Rejected controls preserve both previously configured responses.
            url = f"{server.base_url}{RULES_CONFIG_PATH}/server?dd_env=test"
            assert requests.get(url, timeout=5).status_code == 401
            assert requests.get(url, headers={"Accept": "application/protobuf"}, timeout=5).status_code == 403
        finally:
            server.close()

    @pytest.mark.parametrize("response_format", [None, [], "xml"])
    def test_rejects_invalid_response_format(self, response_format: object) -> None:
        server = MockedBackendServer(port=0)
        try:
            response = requests.post(
                f"{server.base_url}/system-tests/ffe/responses",
                json={"responses": ["valid"], "response_format": response_format},
                timeout=5,
            )
            assert response.status_code == 400
            assert response.json() == {"error": "response_format must be json or protobuf"}
            assert server.ffe_get_requests() == []
        finally:
            server.close()

    def test_protobuf_and_request_capture(self) -> None:
        server = MockedBackendServer(port=0)
        try:
            for channel in ("client", "server"):
                response = requests.get(
                    f"{server.base_url}{RULES_CONFIG_PATH}/{channel}",
                    params={"dd_env": "test env"},
                    headers={"Accept": "application/protobuf", "dd-client-token": "dummy-token"},
                    timeout=5,
                )
                assert response.status_code == 200
                assert response.headers["Content-Type"] == "application/protobuf"
                assert response.headers["ETag"] == WIRE_FIXTURE["rules"]["etag"]
                assert response.content == base64.b64decode(WIRE_FIXTURE["rules"]["response"])
            assert len(server.ffe_get_requests()) == 2
            assert server.ffe_get_requests()[0]["path"] == f"{RULES_CONFIG_PATH}/client?dd_env=test+env"
            assert server.ffe_get_requests()[0]["headers"]["dd-client-token"] == "dummy-token"
            assert extra_hosts_for_environment({"SYSTEM_TESTS_FFE_RULES_BASE_URL": server.ffe_library_base_url}) == (
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
        server = MockedBackendServer(port=0)
        try:
            server.ffe_set_response(mode, response_format="protobuf")
            response = requests.get(f"{server.base_url}{RULES_CONFIG_PATH}/client", timeout=5)
            assert response.status_code == status
            assert response.headers["Content-Type"] == content_type
            assert response.content == body
        finally:
            server.close()

    def test_redirect_records_destination_requests(self) -> None:
        server = MockedBackendServer(port=0)
        try:
            redirect_path = f"{RULES_CONFIG_PATH}/redirected"
            server.ffe_set_response("redirect", response_format="protobuf")
            response = requests.get(f"{server.base_url}{RULES_CONFIG_PATH}/client", allow_redirects=False, timeout=5)
            assert response.status_code == 302
            assert response.headers["Location"] == f"{server.ffe_library_base_url}{redirect_path}"
            server.ffe_set_response("valid", response_format="protobuf")
            requests.get(f"{server.base_url}{redirect_path}", timeout=5).raise_for_status()
            assert len(server.ffe_get_requests()) == 2
            assert server.ffe_get_requests()[1]["path"] == redirect_path
            requests.get(f"{server.base_url}/redirected", timeout=5)
            assert len(server.ffe_get_requests()) == 2
        finally:
            server.close()

    @pytest.mark.parametrize(
        ("mode", "error"),
        [("disconnect", requests.ConnectionError), ("truncated_body", requests.exceptions.ChunkedEncodingError)],
    )
    def test_interrupted_responses(self, mode: str, error: type[requests.RequestException]) -> None:
        server = MockedBackendServer(port=0)
        try:
            server.ffe_set_response(mode, response_format="protobuf")
            with pytest.raises(error):
                requests.get(f"{server.base_url}{RULES_CONFIG_PATH}/client", timeout=5)
            assert len(server.ffe_get_requests()) == 1
        finally:
            server.close()
