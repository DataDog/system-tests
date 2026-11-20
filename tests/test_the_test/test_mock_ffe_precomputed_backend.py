"""Validate the shared precomputed HTTP fixture independently of SDK results."""

import hashlib

import requests

from utils import features, pytest, scenarios
from utils.mocked_backend import MockedBackendServer
from utils.mocked_backend.ffe import PRECOMPUTED_CONFIG_PATH, RULES_CONFIG_PATH


@scenarios.test_the_test
@features.not_reported
class Test_Mock_FFE_Precomputed_Backend:
    def test_response_and_detached_request_capture(self) -> None:
        backend = MockedBackendServer(port=0)
        payload = {
            "data": {"type": "precompute-assignments-request", "attributes": {"subject": {"targeting_key": "subject"}}}
        }
        try:
            response = requests.post(
                f"{backend.base_url}{PRECOMPUTED_CONFIG_PATH}?dd_env=test", json=payload, timeout=5
            )
            assert response.status_code == 200
            assert response.headers["Content-Type"] == "application/vnd.api+json"
            assert response.headers["ETag"] == '"precomputed-v1"'
            data = response.json()["data"]
            assert data["type"] == "precomputed-assignments"
            flags = data["attributes"]["flags"]
            assert flags["test-flag"]["variationValue"] is True
            assert flags["false-flag"]["variationValue"] is False
            assert flags["nullable"]["variationValue"] is None
            captured = backend.ffe_get_requests()
            assert len(captured) == 1
            assert captured[0]["body"] == payload
            captured[0]["body"]["data"]["type"] = "changed"
            assert backend.ffe_get_requests()[0]["body"] == payload
        finally:
            backend.close()

    def test_encoding_timeline_and_reset(self) -> None:
        backend = MockedBackendServer(port=0)
        try:
            backend.client.ffe_set_response("forbidden", response_format="protobuf")
            backend.client.ffe_set_responses(["encoded", "forbidden"], response_format="precomputed")
            url = f"{backend.base_url}{PRECOMPUTED_CONFIG_PATH}"
            response = requests.post(url, json={}, timeout=5)
            attributes = response.json()["data"]["attributes"]
            assert attributes["obfuscated"] is True
            assert attributes["obfuscation"] == {
                "scheme": "flag-key-sha256-v1",
                "salt": "000102030405060708090a0b0c0d0e0f",
            }
            assert set(attributes["flags"]) == {
                hashlib.sha256(b"datadog.feature-flags.flag-key.v1\0" + bytes(range(16)) + key.encode()).hexdigest()
                for key in ("test-flag", "false-flag", "nullable")
            }
            assert requests.post(url, json={}, timeout=5).status_code == 403
            assert requests.get(f"{backend.base_url}{RULES_CONFIG_PATH}/client", timeout=5).status_code == 403
            backend.client.ffe_reset()
            assert backend.ffe_get_requests() == []
            reset = requests.post(url, json={}, timeout=5).json()["data"]["attributes"]
            assert reset["obfuscated"] is False
            assert set(reset["flags"]) == {"test-flag", "false-flag", "nullable"}
        finally:
            backend.close()

    def test_control_validation_and_scripted_policies(self) -> None:
        backend = MockedBackendServer(port=0)
        try:
            with pytest.raises(ValueError, match="unsupported precomputed response"):
                backend.client.ffe_set_response("not_modified", response_format="precomputed")
            assert backend.ffe_get_requests() == []
            for mode, expected in (("opt_out_immediate", "immediate"), ("opt_out_future", "future_experiments_only")):
                backend.client.ffe_set_response(mode, response_format="precomputed")
                response = requests.post(f"{backend.base_url}{PRECOMPUTED_CONFIG_PATH}", json={}, timeout=5)
                assert response.status_code == 200
                assert response.json()["data"]["attributes"]["evaluation_options"] == {
                    "experimentation_opt_out": True,
                    "experimentation_opt_out_mode": expected,
                    "dd_experimentation_opt_out_at": "2026-11-06T12:00:00Z",
                }
        finally:
            backend.close()
