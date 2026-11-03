"""Server SDK flag selection against the mocked FFE agentless backend.

Feature under test: a server SDK given a flag selection sends it on the agentless configuration request and serves
only the flags the backend returns. The cases come from the ffe-system-test-data flag-selection evaluation suite: the
mocked backend serves the suite's ufc-config.json and applies the selection with the suite's flag-tags.json. Each case
file is one provider start.

The selection reaches the SDK as written, through ffe_start's flag_selection field, so the canonical selection on the
request is the SDK's own work. The Node.js test app builds its provider at boot, so it takes the same raw selection
from SYSTEM_TESTS_FFE_FLAG_SELECTION instead.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

from utils import pytest

from tests.parametric.conftest import APMLibrary
from utils import context, features, scenarios
from utils.mocked_backend import MockedBackendServer
from utils.mocked_backend.ffe import (
    EXPECTED_DD_ENV,
    SELECTED_FLAG_KEY_PATTERNS,
    SELECTED_FLAG_TAGS,
    MockedBackendFFERequest,
    Selection,
    ufc_etag_for,
)

SUITE = "flag-selection"
SUITE_CASES_DIR = Path(__file__).parent / "ffe-system-test-data" / "evaluation-suites" / SUITE / "cases"
REVALIDATION_SELECTION = {"tags": ["team:checkout"]}


@dataclass(frozen=True)
class _CaseFile:
    """One provider start: every case in the file shares its selection, request and server response."""

    name: str
    cases: list[dict[str, Any]]

    @property
    def flag_selection(self) -> object:
        return self.cases[0].get("providerOptions", {}).get("flagSelection")

    @property
    def flag_selection_ignored(self) -> str | None:
        return self.cases[0].get("configurationResponse", {}).get("flagSelectionIgnored")

    @property
    def expected_query(self) -> dict[str, list[str]]:
        request = self.cases[0]["expectations"]["configurationRequest"]
        query = {"dd_env": [EXPECTED_DD_ENV]}
        for parameter, field in (
            (SELECTED_FLAG_TAGS, "selectedFlagTags"),
            (SELECTED_FLAG_KEY_PATTERNS, "selectedFlagKeyPatterns"),
        ):
            if request.get(field):
                query[parameter] = request[field]
        return query


def _load_case_files() -> list[_CaseFile]:
    paths = sorted(SUITE_CASES_DIR.glob("*.json"))
    if not paths:
        raise FileNotFoundError(f"No flag selection suite cases found in {SUITE_CASES_DIR}")
    return [_CaseFile(path.stem, json.loads(path.read_text(encoding="utf-8"))) for path in paths]


CASE_FILES = _load_case_files()


def _applies_to(case: dict[str, Any], platform: str) -> bool:
    skipped = {entry["platform"] for entry in case.get("_skip", [])}
    included = {entry["platform"] for entry in case.get("_include", [])}
    return platform not in skipped and (not included or platform in included)


def _agentless_env(mocked_backend: MockedBackendServer, flag_selection: object) -> dict[str, str]:
    env = {
        "DD_API_KEY": scenarios.parametric.dd_api_key,
        "DD_INSTRUMENTATION_TELEMETRY_ENABLED": "false",
        "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE": "agentless",
        "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL": mocked_backend.ffe_library_config_url,
        "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_POLL_INTERVAL_SECONDS": "1",
    }
    if flag_selection is not None:
        env["SYSTEM_TESTS_FFE_FLAG_SELECTION"] = json.dumps(flag_selection)
    return env


def _config_requests(mocked_backend: MockedBackendServer, count: int) -> list[MockedBackendFFERequest]:
    deadline = time.monotonic() + 10
    while len(requests := mocked_backend.ffe_get_requests()) < count and time.monotonic() < deadline:
        time.sleep(0.2)
    assert len(requests) >= count, f"the SDK made {len(requests)} configuration requests, expected {count}"
    return requests


def _query(request: MockedBackendFFERequest) -> dict[str, list[str]]:
    return parse_qs(urlsplit(request["path"]).query, keep_blank_values=True)


def _is_waiting_for_config(result: dict[str, Any]) -> bool:
    provider_state = result.get("providerState")
    return result.get("errorCode") == "PROVIDER_NOT_READY" or (
        isinstance(provider_state, dict) and provider_state.get("hasConfig") is False
    )


def _evaluate(test_library: APMLibrary, case: dict[str, Any]) -> dict[str, Any]:
    for _ in range(10):
        result = test_library.ffe_evaluate(
            flag=case["flag"],
            variation_type=case["variationType"],
            default_value=case["defaultValue"],
            targeting_key=case["targetingKey"],
            attributes=case["attributes"],
        )
        if not _is_waiting_for_config(result):
            break
        time.sleep(0.2)
    return result


@scenarios.parametric
@features.feature_flags_configuration_filtering
class Test_FFE_Flag_Selection:
    @pytest.fixture
    def library_env(self, mocked_backend: MockedBackendServer, case_file: _CaseFile) -> dict[str, str]:
        # Some SDKs fetch their configuration as soon as the library starts.
        mocked_backend.client.ffe_use_suite(SUITE)
        if case_file.flag_selection_ignored is not None:
            mocked_backend.client.ffe_set_flag_selection_ignored_reason(case_file.flag_selection_ignored)
        return _agentless_env(mocked_backend, case_file.flag_selection)

    @pytest.mark.parametrize("case_file", CASE_FILES, ids=[case_file.name for case_file in CASE_FILES])
    def test_flag_selection_suite(
        self, case_file: _CaseFile, test_library: APMLibrary, mocked_backend: MockedBackendServer
    ) -> None:
        cases = [case for case in case_file.cases if _applies_to(case, context.library.name)]
        if not cases:
            pytest.skip(f"No cases in {case_file.name} apply to {context.library.name}")

        assert test_library.ffe_start(flag_selection=case_file.flag_selection), "Failed to start FFE provider"
        request = _config_requests(mocked_backend, 1)[0]
        assert _query(request) == case_file.expected_query, (
            f"{case_file.name}: the configuration request does not carry the expected selection"
        )

        for index, case in enumerate(cases):
            expected = case["result"]
            result = _evaluate(test_library, case)
            location = f"{case_file.name} case {index} ({case['flag']})"
            assert not _is_waiting_for_config(result), f"{location}: the provider loaded no configuration: {result}"
            assert result.get("value") == expected["value"], f"{location}: {result}"
            assert result.get("reason") == expected["reason"], f"{location}: {result}"
            if "errorCode" in expected:
                assert result.get("errorCode") == expected["errorCode"], f"{location}: {result}"
            else:
                assert result.get("errorCode") in {None, ""}, f"{location}: {result}"


@scenarios.parametric
@features.feature_flags_configuration_filtering
class Test_FFE_Flag_Selection_Revalidation:
    @pytest.fixture
    def library_env(self, mocked_backend: MockedBackendServer) -> dict[str, str]:
        mocked_backend.client.ffe_use_suite(SUITE)
        mocked_backend.client.ffe_set_responses(["valid", "not_modified"])
        return _agentless_env(mocked_backend, REVALIDATION_SELECTION)

    def test_selected_configuration_revalidates_with_its_etag(
        self, test_library: APMLibrary, mocked_backend: MockedBackendServer
    ) -> None:
        assert test_library.ffe_start(flag_selection=REVALIDATION_SELECTION), "Failed to start FFE provider"
        assert _query(_config_requests(mocked_backend, 1)[0]) == {
            "dd_env": [EXPECTED_DD_ENV],
            SELECTED_FLAG_TAGS: ["team:checkout"],
        }, "the configuration request does not carry the selection"

        assert _config_requests(mocked_backend, 2)[1]["headers"].get("if-none-match") == ufc_etag_for(
            Selection(tags=("team:checkout",), key_patterns=()), SUITE
        ), "the SDK did not revalidate with the ETag of its selection"
