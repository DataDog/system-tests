"""Standalone client-channel precomputed fetching through real HTTP and portable codecs."""

import hashlib
import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

from utils import features, pytest, scenarios, slow
from utils.docker_fixtures import ParametricTestClientApi as APMLibrary
from utils.mocked_backend import MockedBackendServer
from utils.mocked_backend.ffe import PRECOMPUTED_CONFIG_PATH, RESPONSE_SECRET

TOKEN = "system-tests-private-client-token"
HASH_CAPABILITY = "assignment-encoding-flag-key-256-v1"
DEPENDENT_CAPABILITY = "dependent-flag-variant-key-v1"
CONTEXT = {
    "targetingKey": "subject",
    "country": "US",
    "count": 3,
    "enabled": False,
    "nested": {"tags": ["a"]},
    "empty": None,
}
OPTIONS = {"distributionChannel": "client", "clientToken": TOKEN, "env": "test & preview", "context": CONTEXT}
CUTOFF = "2026-11-06T12:00:00Z"


def fingerprint(*capabilities: str) -> str:
    return json.dumps(
        {"version": 1, "sdk": {"name": "browser", "version": "system-test"}, "capabilities": capabilities}
    )


@pytest.fixture
def library_env(mocked_backend: MockedBackendServer) -> dict[str, str]:
    return {"SYSTEM_TESTS_FFE_RULES_BASE_URL": mocked_backend.ffe_library_base_url}


def snapshot(result: dict[str, Any], *, exposure_events: int = 0) -> tuple[dict[str, Any], dict[str, Any]]:
    assert "error" not in result, result
    wire = json.loads(result["wire"])
    assert json.loads(result["restored"]) == wire
    assert set(wire) == {"version", "precomputed"}
    assert result["httpRequests"] == 1
    assert result["exposureEvents"] == exposure_events
    assert result["exposuresBeforeTracking"] == 0
    portable = wire["precomputed"]
    assert portable["etag"] == '"precomputed-v1"'
    assert portable["fetchedAt"] > 0
    return wire, json.loads(portable["response"])["data"]["attributes"]


def assert_error(result: dict[str, Any], code: str, *, requests: int, status: int | None = None) -> None:
    assert "wire" not in result, result
    assert result["error"]["name"] == "ConfigurationFetchError", result
    assert result["error"]["code"] == code, result
    assert result["error"].get("status") == status, result
    assert result["httpRequests"] == requests, result
    assert result["exposureEvents"] == 0, result
    for secret in (TOKEN, RESPONSE_SECRET, "private-cancellation-reason", "private-invalid"):
        assert secret not in json.dumps(result)


@scenarios.parametric
@features.feature_flags_portable_configuration
@slow
class Test_FFE_Precomputed_Configuration:
    def test_request_wire_and_context_binding(
        self, test_library: APMLibrary, mocked_backend: MockedBackendServer
    ) -> None:
        with test_library:
            for entry in ("root", "rules-based"):
                count = len(mocked_backend.ffe_get_requests())
                result = test_library.ffe_fetch_precomputed_configuration(
                    {
                        "entryPoint": entry,
                        "mutateContext": True,
                        "contexts": [CONTEXT, {**CONTEXT, "targetingKey": "another-subject"}],
                        "options": {
                            **OPTIONS,
                            "site": "datad0g.com",
                            "applicationId": "application",
                            "clientFingerprint": fingerprint(HASH_CAPABILITY, DEPENDENT_CAPABILITY, "unknown-v1"),
                        },
                    }
                )
                wire, attributes = snapshot(result)
                request_url = urlsplit(result["requestUrl"])
                assert request_url.scheme == "https"
                assert request_url.netloc == "preview.ff-cdn.datad0g.com"
                assert result["providerStatus"] == "READY"
                assert wire["version"] == 1
                assert wire["precomputed"]["context"] == CONTEXT
                assert attributes["environment"] == {"name": "test"}
                assert attributes["observeFullEvaluationData"] is False
                flags = attributes["flags"]
                assert set(flags) == {"test-flag", "false-flag", "nullable"}
                assert flags["false-flag"]["variationValue"] is False
                assert flags["nullable"]["variationValue"] is None
                assert flags["test-flag"]["features"] == [
                    {"key": "checkout", "value": False, "destinations": ["HOOK", "EXPOSURE"]}
                ]
                success, mismatch = result["results"]
                assert success["value"] is True
                assert success["reason"] == "TARGETING_MATCH"
                assert success["variant"] == "on"
                assert success.get("errorCode") is None
                assert success["flagMetadata"]["__dd_split_serial_id"] == 7
                assert success["flagMetadata"]["__dd_do_log"] is True
                assert result["nullable"]["value"] is None
                assert result["nullable"].get("errorCode") is None
                assert mismatch["value"] is False
                assert mismatch["errorCode"] == "INVALID_CONTEXT"
                requests = mocked_backend.ffe_get_requests()[count:]
                assert len(requests) == 1
                request = requests[0]
                url = urlsplit(request["path"])
                assert url.path == PRECOMPUTED_CONFIG_PATH
                assert parse_qs(url.query) == {"dd_env": ["test & preview"], "cap_dependent-flags-variant-key": ["v1"]}
                headers = request["headers"]
                assert headers["dd-client-token"] == TOKEN
                assert headers["dd-application-id"] == "application"
                assert headers["accept"] == headers["content-type"] == "application/vnd.api+json"
                assert "dd-api-key" not in headers
                assert "x-dd-feature-flags-capabilities" not in headers
                body = request["body"]
                assert body["data"]["type"] == "precompute-assignments-request"
                sent = body["data"]["attributes"]
                assert set(sent) == {"env", "source", "subject"}
                assert sent["env"] == {"dd_env": "test & preview"}
                assert sent["source"]["sdk_name"] == "nodejs"
                assert sent["source"]["sdk_version"]
                assert "__BUILD_ENV__" not in sent["source"]["sdk_version"]
                assert sent["subject"] == {
                    "targeting_key": "subject",
                    "targeting_attributes": {
                        "targetingKey": "subject",
                        "country": "US",
                        "count": "3",
                        "enabled": "false",
                        "nested": '{"tags":["a"]}',
                        "empty": "null",
                    },
                }

            # Same observer and fetched input, now with an explicitly enabled SDK sink.
            control = test_library.ffe_fetch_precomputed_configuration({"options": OPTIONS, "trackExposures": True})
            snapshot(control, exposure_events=2)
            assert control["providerStatus"] == "READY"
            assert control["results"][0]["value"] is True
            assert control["results"][0].get("errorCode") is None
            assert control["nullable"]["value"] is None
            assert control["nullable"].get("errorCode") is None

    def test_fingerprint_response_validation(
        self, test_library: APMLibrary, mocked_backend: MockedBackendServer
    ) -> None:
        with test_library:
            for value in (None, fingerprint(), fingerprint("unknown-v1"), fingerprint(HASH_CAPABILITY)):
                mocked_backend.client.ffe_set_response("valid", response_format="precomputed")
                result = test_library.ffe_fetch_precomputed_configuration(
                    {"options": {**OPTIONS, **({"clientFingerprint": value} if value else {})}}
                )
                wire, attributes = snapshot(result)
                assert wire["version"] == 1
                assert attributes["obfuscated"] is False
                assert parse_qs(urlsplit(mocked_backend.ffe_get_requests()[-1]["path"]).query) == {
                    "dd_env": ["test & preview"]
                }
            mocked_backend.client.ffe_set_response("encoded", response_format="precomputed")
            encoded = test_library.ffe_fetch_precomputed_configuration(
                {"options": {**OPTIONS, "clientFingerprint": fingerprint(HASH_CAPABILITY)}}
            )
            wire, attributes = snapshot(encoded)
            assert wire["version"] == 2
            assert attributes["obfuscated"] is True
            salt = bytes.fromhex(attributes["obfuscation"]["salt"])
            assert attributes["obfuscation"]["scheme"] == "flag-key-sha256-v1"
            assert set(attributes["flags"]) == {
                hashlib.sha256(b"datadog.feature-flags.flag-key.v1\0" + salt + key.encode()).hexdigest()
                for key in ("test-flag", "false-flag", "nullable")
            }
            assert encoded["results"][0]["value"] is True
            assert encoded["results"][0].get("errorCode") is None
            for mode, extra in (
                ("encoded", {}),
                ("unknown_encoding", {"clientFingerprint": fingerprint(HASH_CAPABILITY)}),
            ):
                mocked_backend.client.ffe_set_response(mode, response_format="precomputed")
                result = test_library.ffe_fetch_precomputed_configuration({"options": {**OPTIONS, **extra}})
                assert_error(result, "decode", requests=1)

    def test_selection_and_diagnostics(self, test_library: APMLibrary, mocked_backend: MockedBackendServer) -> None:
        cases: list[tuple[str, Any, dict[str, list[str]] | None, str | None]] = [
            (
                "valid",
                {"tags": [" payments ", "checkout", "checkout"], "keyPatterns": ["test-*", "nullable"]},
                {"tags": ["checkout", "payments"], "key_patterns": ["nullable", "test-*"]},
                None,
            ),
            ("selected_empty", {"keyPatterns": ["no-match-*"]}, {"tags": [], "key_patterns": ["no-match-*"]}, None),
            (
                "selection_ignored_tag_load_failed",
                {"tags": ["checkout"]},
                {"tags": ["checkout"], "key_patterns": []},
                "tag_load_failed",
            ),
            ("valid", {"tags": "private-invalid"}, None, "malformed_selection"),
            ("valid", {"tags": [f"tag-{i}" for i in range(32)]}, None, "too_many_values"),
            ("valid", {"tags": [], "keyPatterns": []}, None, None),
        ]
        with test_library:
            for mode, selection, sent, diagnostic in cases:
                mocked_backend.client.ffe_set_response(mode, response_format="precomputed")
                result = test_library.ffe_fetch_precomputed_configuration(
                    {"options": {**OPTIONS, "flagSelection": selection}}
                )
                _, attributes = snapshot(result)
                request = mocked_backend.ffe_get_requests()[-1]
                assert request["body"]["data"]["attributes"].get("flag_selection") == sent
                if mode == "selected_empty":
                    assert attributes["flags"] == {}
                    assert result["results"][0]["value"] is False
                    assert result["results"][0]["errorCode"] == "FLAG_NOT_FOUND"
                else:
                    assert "test-flag" in attributes["flags"]
                    assert result["results"][0]["value"] is True
                assert len(result["diagnostics"]) == (1 if diagnostic else 0)
                if diagnostic:
                    assert diagnostic in result["diagnostics"][0]
                assert "private-invalid" not in json.dumps(result)

    def test_experimentation_opt_out_acknowledgment(
        self, test_library: APMLibrary, mocked_backend: MockedBackendServer
    ) -> None:
        context = {**CONTEXT, "dd_experimentation_opt_out_at": CUTOFF}
        with test_library:
            for mode, response, other_mode in (
                ("immediate", "opt_out_immediate", "opt_out_future"),
                ("future_experiments_only", "opt_out_future", "opt_out_immediate"),
            ):
                options = {**OPTIONS, "context": context, "experimentationOptOutMode": mode}
                mocked_backend.client.ffe_set_response(response, response_format="precomputed")
                result = test_library.ffe_fetch_precomputed_configuration(
                    {"options": options, "evaluate": mode == "immediate"}
                )
                wire, attributes = snapshot(result)
                assert wire["precomputed"]["context"] == context
                assert attributes["evaluation_options"]["experimentation_opt_out"] is True
                assert attributes["evaluation_options"]["experimentation_opt_out_mode"] == mode
                if mode == "immediate":
                    assert result["results"][0]["value"] is True
                    assert result["results"][0].get("errorCode") is None
                assert mocked_backend.ffe_get_requests()[-1]["body"]["data"]["attributes"]["evaluation_options"] == {
                    "experimentation_opt_out_mode": mode
                }
                for invalid_response in ("valid", other_mode, "opt_out_mismatch"):
                    mocked_backend.client.ffe_set_response(invalid_response, response_format="precomputed")
                    invalid = test_library.ffe_fetch_precomputed_configuration({"options": options, "evaluate": False})
                    assert_error(invalid, "decode", requests=1)
            mocked_backend.client.ffe_set_response("opt_out_immediate", response_format="precomputed")
            invalid = test_library.ffe_fetch_precomputed_configuration({"options": OPTIONS})
            assert_error(invalid, "decode", requests=1)

    def test_transport_failures(self, test_library: APMLibrary, mocked_backend: MockedBackendServer) -> None:
        cases = [
            ("forbidden", "http", 403),
            ("server_error", "http", 500),
            ("redirect", "http", 302),
            ("malformed", "decode", None),
            ("invalid_response", "decode", None),
            ("empty", "decode", None),
            ("wrong_content_type", "invalid_response", None),
            ("disconnect", "transport", None),
            ("truncated_body", "transport", None),
        ]
        with test_library:
            for response, code, status in cases:
                mocked_backend.client.ffe_set_response(response, response_format="precomputed")
                count = len(mocked_backend.ffe_get_requests())
                result = test_library.ffe_fetch_precomputed_configuration({"options": OPTIONS})
                assert_error(result, code, requests=1, status=status)
                assert len(mocked_backend.ffe_get_requests()) == count + 1

    def test_deadlines_and_cancellation(self, test_library: APMLibrary, mocked_backend: MockedBackendServer) -> None:
        with test_library:
            for response in ("delayed", "delayed_body"):
                for cancel in (False, True):
                    mocked_backend.client.ffe_set_response(response, response_format="precomputed")
                    count = len(mocked_backend.ffe_get_requests())
                    result = test_library.ffe_fetch_precomputed_configuration(
                        {
                            "options": {**OPTIONS, "timeoutMs": 5000 if cancel else 2000},
                            **({"abortAfterMs": 2000} if cancel else {}),
                        }
                    )
                    assert_error(result, "cancelled" if cancel else "timeout", requests=1)
                    assert len(mocked_backend.ffe_get_requests()) == count + 1
            count = len(mocked_backend.ffe_get_requests())
            result = test_library.ffe_fetch_precomputed_configuration({"options": OPTIONS, "abort": True})
            assert_error(result, "cancelled", requests=0)
            assert len(mocked_backend.ffe_get_requests()) == count

    def test_invalid_options_do_not_send(self, test_library: APMLibrary, mocked_backend: MockedBackendServer) -> None:
        cases: list[dict[str, Any]] = [
            {"distributionChannel": "server"},
            {"distributionChannel": None},
            {"apiKey": "private-invalid-api-key"},
            {"clientToken": ""},
            {"clientToken": "private-invalid\r\nheader"},
            {"env": " "},
            {"site": "example.invalid"},
            {"applicationId": "\nprivate-invalid"},
            {"context": None},
            {"context": {"targetingKey": 42}},
            {"context": ["private-invalid"]},
            {"timeoutMs": 0},
            {"clientFingerprint": "private-invalid"},
            {"clientFingerprint": json.dumps({"version": 999})},
            {"experimentationOptOutMode": "private-invalid"},
            {
                "experimentationOptOutMode": "immediate",
                "context": {**CONTEXT, "dd_experimentation_opt_out_at": "private-invalid"},
            },
        ]
        with test_library:
            for extra in cases:
                result = test_library.ffe_fetch_precomputed_configuration({"options": {**OPTIONS, **extra}})
                assert_error(result, "invalid_options", requests=0)
        assert mocked_backend.ffe_get_requests() == []
