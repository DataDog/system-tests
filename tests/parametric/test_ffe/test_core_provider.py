"""Offline provider lifecycle through the real OpenFeature SDK, isolated from the tracer."""

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from utils import features, pytest, scenarios, slow
from utils.docker_fixtures import ParametricTestClientApi as APMLibrary
from utils.mocked_backend import MockedBackendServer
from utils.mocked_backend.ffe import RULES_CONFIG_PATH, load_rules_wire_fixture

WIRE = (Path(__file__).parent / "core-provider-rules-wire.json").read_text()
FETCHED_WIRE = json.dumps(load_rules_wire_fixture())
CONTEXTS = [
    {"targetingKey": "subject-us", "country": "US", "dd_assignment_token": "private-token-us"},
    {"targetingKey": "subject-fr", "country": "FR", "dd_assignment_token": "private-token-fr"},
]


@pytest.fixture
def library_env(mocked_backend: MockedBackendServer) -> dict[str, str]:
    return {"SYSTEM_TESTS_FFE_RULES_BASE_URL": mocked_backend.ffe_library_base_url}


def assert_evaluation(result: dict[str, Any], *, value: bool, variant: str, reason: str) -> None:
    assert result["value"] is value, result
    assert result["variant"] == variant, result
    assert result["reason"] == reason, result
    assert result.get("errorCode") is None, result


def assert_offline(result: dict[str, Any], mocked_backend: MockedBackendServer, *, exposure_events: int = 0) -> None:
    assert result["startup"]["status"] == "READY", result
    assert result["startup"]["readyEvents"] == 1, result
    assert result["startup"]["httpRequests"] == 0, result
    assert result["status"] == "READY", result
    assert result["httpRequests"] == 0, result
    assert result["exposureEvents"] == exposure_events, result
    assert mocked_backend.ffe_get_requests() == []


@scenarios.parametric
@features.feature_flags_portable_configuration
@slow
class Test_FFE_Core_Provider:
    def test_synchronous_bootstrap(self, test_library: APMLibrary, mocked_backend: MockedBackendServer) -> None:
        with test_library:
            result = test_library.ffe_core_provider({"operation": "bootstrap", "wire": WIRE, "contexts": CONTEXTS})

        assert_offline(result, mocked_backend)
        assert result["startup"]["hooks"] == 0
        assert_evaluation(result["results"][0], value=True, variant="on", reason="TARGETING_MATCH")
        assert_evaluation(result["results"][1], value=False, variant="off", reason="SPLIT")

    def test_overlapping_contexts(self, test_library: APMLibrary, mocked_backend: MockedBackendServer) -> None:
        with test_library:
            result = test_library.ffe_core_provider({"operation": "overlap", "wire": WIRE, "contexts": CONTEXTS})

        assert_offline(result, mocked_backend, exposure_events=4)
        assert_evaluation(result["results"][0], value=True, variant="on", reason="TARGETING_MATCH")
        assert_evaluation(result["results"][1], value=False, variant="off", reason="SPLIT")
        observations = {item["subject"]: item for item in result["observations"]}
        assert len(result["observations"]) == 2
        for context, expected in zip(CONTEXTS, [True, False], strict=True):
            observed = observations[context["targetingKey"]]
            assert observed["value"] is expected
            assert len(observed["dependencies"]) == 1
            assert observed["dependencies"][0]["flag"] == "prerequisite"
            assert observed["dependencies"][0]["value"] is expected
            assert observed["consumed"] == []
        exposures = result["exposures"]
        assert len(exposures) == 4, exposures
        assert {(item["subject"]["id"], item["flag"]["key"]) for item in exposures} == {
            (context["targetingKey"], flag) for context in CONTEXTS for flag in ("test-flag", "prerequisite")
        }
        for exposure in exposures:
            expected_country = "US" if exposure["subject"]["id"] == "subject-us" else "FR"
            assert exposure["subject"]["attributes"] == {"country": expected_country}
        assert "private-token" not in json.dumps(result)

    def test_refresh_and_rejected_replacement(
        self, test_library: APMLibrary, mocked_backend: MockedBackendServer
    ) -> None:
        with test_library:
            for response in ("valid", "forbidden"):
                mocked_backend.client.ffe_set_response(response, response_format="protobuf")
                request_count = len(mocked_backend.ffe_get_requests())
                result = test_library.ffe_core_provider(
                    {
                        "operation": "refresh",
                        "wire": WIRE,
                        "replacementWire": WIRE if response == "valid" else FETCHED_WIRE,
                        "contexts": [CONTEXTS[1]],
                        "fetchOptions": {"distributionChannel": "server", "apiKey": "system-tests-key", "env": "test"},
                    }
                )
                assert result["startup"]["status"] == "READY"
                assert result["startup"]["httpRequests"] == 0
                for phase in ("initial", "duringRefresh"):
                    assert_evaluation(result[phase], value=False, variant="off", reason="SPLIT")
                for phase in ("afterFetch", "afterInvalid"):
                    assert_evaluation(
                        result[phase],
                        value=response == "valid",
                        variant="on" if response == "valid" else "off",
                        reason="SPLIT",
                    )
                assert result["invalidUpdateError"] == "TypeError"
                assert result["unchanged"] is True
                if response == "forbidden":
                    assert result["fetchError"] == {"name": "ConfigurationFetchError", "code": "http", "status": 403}
                else:
                    assert "fetchError" not in result
                assert_evaluation(
                    result["afterReplacement"],
                    value=response != "valid",
                    variant="off" if response == "valid" else "on",
                    reason="SPLIT",
                )
                notifications = result["notifications"]
                expected_values = [True, False] if response == "valid" else [True]
                assert len(notifications) == len(expected_values)
                for notification, value in zip(notifications, expected_values, strict=True):
                    assert notification["status"] == "READY"
                    assert_evaluation(
                        notification["result"], value=value, variant="on" if value else "off", reason="SPLIT"
                    )
                assert result["status"] == "READY"
                assert result["httpRequests"] == 1
                assert result["exposureEvents"] == 0
                requests = mocked_backend.ffe_get_requests()[request_count:]
                assert len(requests) == 1, requests
                url = urlsplit(requests[0]["path"])
                assert url.path == f"{RULES_CONFIG_PATH}/server"
                assert parse_qs(url.query) == {"dd_env": ["test"]}
                assert requests[0]["headers"]["dd-api-key"] == "system-tests-key"

    def test_opt_in_exposure_tracking(self, test_library: APMLibrary, mocked_backend: MockedBackendServer) -> None:
        with test_library:
            result = test_library.ffe_core_provider({"operation": "tracking", "wire": WIRE, "contexts": CONTEXTS})

        assert_offline(result, mocked_backend, exposure_events=6)
        assert result["startup"]["hooks"] == 0
        assert result["beforeHook"] == 0
        assert result["deduplicated"] == 2
        assert result["failed"]["reason"] == "ERROR"
        assert result["failed"]["errorCode"] == "GENERAL"
        assert result["afterFailure"] == 2
        assert result["afterRetry"] == 4
        assert result["afterClose"] == 4  # The tracking helper owns this cache, not the provider.
        exposures = result["exposures"]
        assert len(exposures) == 6
        assert {(item["subject"]["id"], item["flag"]["key"], item["variant"]["key"]) for item in exposures[:4]} == {
            (context["targetingKey"], flag, "on" if context["country"] == "US" else "off")
            for context in CONTEXTS
            for flag in ("test-flag", "prerequisite")
        }
        assert "private-token" not in json.dumps(result)
