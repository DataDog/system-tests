"""Standalone SSR producer contract; intentionally does not initialize a browser SDK."""

import base64
import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

from utils import features, pytest, scenarios, slow
from utils.docker_fixtures import ParametricTestClientApi as APMLibrary
from utils.mocked_backend import MockedBackendServer
from utils.mocked_backend.ffe import RULES_CONFIG_PATH, RESPONSE_SECRET, load_rules_wire_fixture

WIRE_FIXTURE = load_rules_wire_fixture()
CLIENT_TOKEN = "system-tests-client-token"
API_KEY = "system-tests-api-key"
CLIENT_OPTIONS = {"distributionChannel": "client", "clientToken": CLIENT_TOKEN, "env": "test env"}


@pytest.fixture
def library_env(mocked_backend: MockedBackendServer) -> dict[str, str]:
    return {"SYSTEM_TESTS_FFE_RULES_BASE_URL": mocked_backend.ffe_library_base_url}


@scenarios.parametric
@features.feature_flags_portable_configuration
@slow
class Test_FFE_Rules_Configuration:
    def test_fetch_and_serialize(self, test_library: APMLibrary, mocked_backend: MockedBackendServer) -> None:
        with test_library:
            for channel in (None, "server", "client"):
                case = channel or "default-server"
                options: dict[str, Any] = {"env": "test env"}
                if channel is not None:
                    options["distributionChannel"] = channel
                credential = "clientToken" if channel == "client" else "apiKey"
                options[credential] = CLIENT_TOKEN if channel == "client" else API_KEY
                request_count = len(mocked_backend.ffe_get_requests())
                result = test_library.ffe_fetch_rules_configuration(options)

                assert "error" not in result, (case, result)
                assert isinstance(result["wire"], str), case
                wire = json.loads(result["wire"])
                assert wire["version"] == WIRE_FIXTURE["version"], case
                # Protobuf re-encoding can omit defaults or pack fields differently.
                # Consumer-side semantic round trips are covered by the SDK package tests.
                assert base64.b64decode(wire["rules"]["response"], validate=True), case
                assert wire["rules"]["etag"] == WIRE_FIXTURE["rules"]["etag"], case
                assert isinstance(wire["rules"]["fetchedAt"], (int, float)), case
                assert wire["rules"]["fetchedAt"] > 0, case
                assert CLIENT_TOKEN not in result["wire"], case
                assert API_KEY not in result["wire"], case

                requests = mocked_backend.ffe_get_requests()[request_count:]
                assert len(requests) == 1, (case, requests)
                url = urlsplit(requests[0]["path"])
                assert url.path == f"{RULES_CONFIG_PATH}/{channel or 'server'}", case
                assert parse_qs(url.query) == {"dd_env": ["test env"]}, case
                headers = requests[0]["headers"]
                assert headers["accept"] == "application/protobuf", case
                assert headers.get("dd-client-token") == (CLIENT_TOKEN if channel == "client" else None), case
                assert headers.get("dd-api-key") == (None if channel == "client" else API_KEY), case
                assert headers["dd-client-library-language"] == "nodejs", case
                assert headers["dd-client-library-version"], case
                assert "__BUILD_ENV__" not in headers["dd-client-library-version"], case

    def test_fetch_failure(self, test_library: APMLibrary, mocked_backend: MockedBackendServer) -> None:
        cases: list[tuple[str, str, int | None]] = [
            ("forbidden", "http", 403),
            ("server_error", "http", 500),
            ("redirect", "http", 302),
            ("malformed", "decode", None),
            ("empty", "invalid_response", None),
            ("wrong_content_type", "invalid_response", None),
            ("disconnect", "transport", None),
            ("truncated_body", "transport", None),
        ]
        with test_library:
            for response, code, status in cases:
                mocked_backend.ffe_set_response(response, response_format="protobuf")
                request_count = len(mocked_backend.ffe_get_requests())
                result = test_library.ffe_fetch_rules_configuration(CLIENT_OPTIONS)

                assert "wire" not in result, (response, result)
                error = result["error"]
                assert error["name"] == "ConfigurationFetchError", (response, result)
                assert error["code"] == code, (response, result)
                assert error.get("status") == status, (response, result)
                assert CLIENT_TOKEN not in json.dumps(result), response
                assert RESPONSE_SECRET not in json.dumps(result), response
                # Includes redirect protection: no follow-up request or automatic retry.
                requests = mocked_backend.ffe_get_requests()[request_count:]
                assert len(requests) == 1, (response, requests)

    @pytest.mark.parametrize("response", ["delayed", "delayed_body"], ids=["headers", "body"])
    def test_fetch_timeout(self, test_library: APMLibrary, mocked_backend: MockedBackendServer, response: str) -> None:
        mocked_backend.ffe_set_response(response, response_format="protobuf")
        # Allow connection setup, but expire before the full delayed response arrives.
        with test_library:
            result = test_library.ffe_fetch_rules_configuration({**CLIENT_OPTIONS, "timeoutMs": 2000})

        assert "wire" not in result
        error = result["error"]
        assert error["name"] == "ConfigurationFetchError"
        assert error["code"] == "timeout"
        assert error.get("status") is None
        assert CLIENT_TOKEN not in json.dumps(result)
        assert RESPONSE_SECRET not in json.dumps(result)
        assert len(mocked_backend.ffe_get_requests()) == 1

    @pytest.mark.parametrize("response", ["delayed", "delayed_body"], ids=["headers", "body"])
    def test_cancel_in_flight(
        self, test_library: APMLibrary, mocked_backend: MockedBackendServer, response: str
    ) -> None:
        mocked_backend.ffe_set_response(response, response_format="protobuf")
        with test_library:
            result = test_library.ffe_fetch_rules_configuration({**CLIENT_OPTIONS, "abortAfterMs": 2000})

        assert "wire" not in result
        assert result["error"]["name"] == "ConfigurationFetchError"
        assert result["error"]["code"] == "cancelled"
        assert result["error"].get("status") is None
        assert "private-cancellation-reason" not in json.dumps(result)
        assert CLIENT_TOKEN not in json.dumps(result)
        assert len(mocked_backend.ffe_get_requests()) == 1

    def test_cancel_before_request(self, test_library: APMLibrary, mocked_backend: MockedBackendServer) -> None:
        with test_library:
            result = test_library.ffe_fetch_rules_configuration({**CLIENT_OPTIONS, "abort": True})

        assert "wire" not in result
        assert result["error"]["name"] == "ConfigurationFetchError"
        assert result["error"]["code"] == "cancelled"
        assert CLIENT_TOKEN not in json.dumps(result)
        assert API_KEY not in json.dumps(result)
        assert mocked_backend.ffe_get_requests() == []

    def test_reject_invalid_options(self, test_library: APMLibrary, mocked_backend: MockedBackendServer) -> None:
        cases: list[tuple[str, dict[str, Any]]] = [
            ("client-token-with-default-server", {"env": "test", "clientToken": CLIENT_TOKEN}),
            ("both-credentials", {**CLIENT_OPTIONS, "apiKey": API_KEY}),
            ("missing-server-key", {"env": "test"}),
            ("missing-client-token", {"distributionChannel": "client", "env": "test"}),
            ("blank-server-key", {"apiKey": " ", "env": "test"}),
            ("blank-client-token", {**CLIENT_OPTIONS, "clientToken": " "}),
            ("credential-newline", {**CLIENT_OPTIONS, "clientToken": f"{CLIENT_TOKEN}\r\nX-Test: value"}),
            ("invalid-channel", {**CLIENT_OPTIONS, "distributionChannel": "unknown"}),
            ("missing-env", {"apiKey": API_KEY}),
            ("blank-env", {**CLIENT_OPTIONS, "env": " "}),
            ("unknown-site", {**CLIENT_OPTIONS, "site": "datadoghq.com.attacker.invalid"}),
            ("site-with-path", {**CLIENT_OPTIONS, "site": "datadoghq.com/path"}),
            ("zero-timeout", {**CLIENT_OPTIONS, "timeoutMs": 0}),
            ("negative-timeout", {**CLIENT_OPTIONS, "timeoutMs": -1}),
        ]
        # Share the container; the endpoint still starts a fresh helper process for each case.
        with test_library:
            for case, options in cases:
                result = test_library.ffe_fetch_rules_configuration(options)
                assert "wire" not in result, (case, result)
                assert result["error"]["name"] == "ConfigurationFetchError", (case, result)
                assert result["error"]["code"] == "invalid_options", (case, result)
                assert CLIENT_TOKEN not in json.dumps(result), case
                assert API_KEY not in json.dumps(result), case
                assert mocked_backend.ffe_get_requests() == [], case
